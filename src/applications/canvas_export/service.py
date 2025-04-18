from datetime import datetime, timezone
import os
from dotenv import load_dotenv
from fastapi import HTTPException
from pymongo import UpdateOne
from pymongo.database import Database
from typing import Dict, List
import requests

from src.applications.canvas_export.constants import EnrollmentRole, EnrollmentStatus, UserStatus
from src.applications.canvas_export.schemas import SISImportObject, SISUserObject
from src.applications.canvas_export.utils import get_csv_as_tmp_file
from src.applications.models import ApplicationModel
from src.config import APPLICATIONS_COLLECTION, settings

def get_unenrolled_application_documents(db: Database) -> List[ApplicationModel]:
    """
    Get Application documents from Mongo collection.

    This function finds Application documents as ApplicationModel objects and returns them as a list.
    HTTPException is raised if there is a DB error or no Applications are found.
    """
    application_collection = db.get_collection(APPLICATIONS_COLLECTION)
    applications_cursor = application_collection.find({"canvas_id": None})

    application_documents = applications_cursor.to_list()
    if len(application_documents) == 0:
        raise HTTPException(status_code=404, detail=f"No unenrolled applicants found.")
    
    return [ApplicationModel(**application) for application in application_documents]

def generate_users_csv(application_documents: List[ApplicationModel] = []) -> str:
    """
    Converts ApplicationModel list into CSV stream data following Canvas' Users.csv format.
    """
    users_csv_headers = [
        "user_id",
        "integration_id",
        "login_id",
        "password",
        "first_name",
        "last_name",
        "full_name",
        "sortable_name",
        "short_name",
        "email",
        "status"
    ]

    # extract the data from the Application documents for each CSV row
    users_csv_rows = []
    for application_document in application_documents:
        user_row = [None] * len(users_csv_headers)

        user_row[0] = application_document.email
        user_row[2] = application_document.email
        user_row[4] = application_document.fname
        user_row[5] = application_document.lname
        user_row[9] = application_document.email
        user_row[10] = UserStatus.ACTIVE.value

        users_csv_rows.append(user_row)

    csv_full_path = get_csv_as_tmp_file(
        headers=users_csv_headers,
        rows=users_csv_rows,
        filename="Users"
    )
    
    return csv_full_path

def generate_unterview_enrollments_csv(application_documents: List[ApplicationModel] = []) -> str:
    """
    Converts ApplicationModel list into CSV stream data following Canvas' Enrollments.csv format.
    """
    
    enrollments_csv_headers = [
        "course_id", # todo: may not be required with section_id
        "user_id",
        "role",
        "section_id", # todo: may not be required with course_id
        "status"
    ]

    # extract the data from the Application documents for each CSV row
    enrollments_csv_rows = []
    for application_document in application_documents:
        enrollment_row = [None] * len(enrollments_csv_headers)

        enrollment_row[0] = settings.unterview_id
        enrollment_row[1] = application_document.email
        enrollment_row[2] = EnrollmentRole.STUDENT.value
        enrollment_row[3] = settings.current_section
        enrollment_row[4] = EnrollmentStatus.ACTIVE.value

        enrollments_csv_rows.append(enrollment_row)

    csv_full_path = get_csv_as_tmp_file(
        headers=enrollments_csv_headers,
        rows=enrollments_csv_rows,
        filename="Enrollments"
    )
    
    return csv_full_path

def send_sis_csv(csv: str) -> SISImportObject:
    """
    Sends CSV file to Canvas API, updating respective data.
    """
    test_url = settings.canvas_api_url
    load_dotenv()
    access_token = os.environ.get("CTI_ACCESS_TOKEN")
    if access_token is None:
        return {"Error": "Access token not found"}

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "text/csv"
    }

    with open(csv, "rb") as file:
        response = requests.get(
            url=f"{test_url}/api/v1/accounts/1",
            headers=headers,
            data=file
        )
    
    return response.json()

def get_unterview_enrollments():
    # may require pagination for parsing through the enrollments
    # GET /api/v1/courses/:course_id/search_users
    # NOTE this will call over a pagination of 3800+ students
    # NOTE each page will limit to 100 Users 
    # NOTE could grab only the "invited" users -> may lead to race condition if student accepts
    # FIXME instead of a course call, make it a section call? -> still 1650 students
    """
    Get the users (students) enrolled in the Unterview course.
    """
    test_url = settings.canvas_api_url
    load_dotenv()
    access_token = os.environ.get("CTI_ACCESS_TOKEN")
    if access_token is None:
        return {"Error": "Access token not found"}

    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    response = requests.get(
        url=f"{test_url}/api/v1/courses/{settings.unterview_id}/search_users?enrollment_state=invited&per_page=100",
        headers=headers
    )
    print(response.status_code)
    # print(len(response.json()["students"]))

    return response.json()

def patch_applicants_with_unterview(
    db: Database,
    application_documents: List[ApplicationModel],
    unterview_enrollments: List[SISUserObject],
    batch_date: datetime
) -> int:
    """
    Updates Application documents in-place and bulk writes to MongoDB.

    This function updates the application_documents parameter passed in-place, and
    it returns the number of successfully modified documents from the DB bulk_write.
    """

    # create dictionary mapping application_documents_email to index
    applicant_email_to_index: Dict[str, ApplicationModel] = {}
    for index_for_email in range(0, len(application_documents)):
        applicant_email_to_index[application_documents[index_for_email].email] = index_for_email

    write_operations: List[UpdateOne] = []

    # use dictionary to update documents based on Unterview-enrolled Users
    for enrolled_user in unterview_enrollments:
        index_of_user = applicant_email_to_index.get(enrolled_user.email)

        # skip enrollments not based on applications
        if index_of_user is None:
            continue

        # update the document
        application_document: ApplicationModel = application_documents[index_of_user]
        application_document.added_unterview_course = True
        application_document.canvas_id = enrolled_user.id

        # queue update for database operation
        write_operations.append(
            UpdateOne(
                filter={"email": application_document.email},
                update={"$set": {
                    "canvas_id": application_document.canvas_id,
                    "added_unterview_course": application_document.added_unterview_course,
                    "last_batch_update": batch_date
                }}
            )
        )
    
    return db.get_collection(APPLICATIONS_COLLECTION).bulk_write(write_operations).modified_count

def add_applicants_to_canvas(db: Database):
    """
    Entry function for adding applicants to Canvas and the Unterview course.
    """
    # return get_unterview_enrollments()
    
    batch_date = datetime.now(timezone.utc)

    # fetch documents
    application_documents = get_unenrolled_application_documents(db=db)

    # generate and send CSVs (users.csv and enrollments.csv)
    users_csv = generate_users_csv(application_documents=application_documents)
    enrollments_csv = generate_unterview_enrollments_csv(application_documents=application_documents)

    send_sis_csv(csv=users_csv)
    send_sis_csv(csv=enrollments_csv)

    # delete temp csv files
    os.remove(users_csv)
    os.remove(enrollments_csv)

    # fetch enrollments for current section
    unterview_enrollments = get_unterview_enrollments()

    # update documents with Canvas information
    patch_applicants_with_unterview(
        db=db,
        application_documents=application_documents,
        unterview_enrollments=unterview_enrollments,
        batch_date=batch_date
    )

    # respond with success, number of updated documents, batch date
    return {"success": True, "path": users_csv}
