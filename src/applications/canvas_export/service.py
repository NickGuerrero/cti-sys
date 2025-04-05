import os
from fastapi import HTTPException
from pymongo.database import Database
from typing import List

from src.applications.canvas_export.constants import EnrollmentRole, EnrollmentStatus, UserStatus
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

    csv_full_path = get_csv_as_tmp_file(headers=users_csv_headers, rows=users_csv_rows, filename="Users")
    
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

    csv_full_path = get_csv_as_tmp_file(headers=enrollments_csv_headers, rows=enrollments_csv_rows, filename="Enrollments")
    
    return csv_full_path

def send_sis_csv(csv: str):
    """
    Sends CSV file to Canvas API, updating respective data.

    todo: This will require an access token and/or authorization parameters with write scope.
    todo: look into the size issues or whether a stream can be sent out vs a file as saved.
    """
    pass

def get_unterview_enrollments():
    # may require pagination for parsing through the enrollments
    pass

def patch_applicants_with_unterview(application_documents, unterview_enrollments):
    pass

def add_applicants_to_canvas(db: Database):
    """
    Entry function for adding applicants to Canvas and the Unterview course.
    """
    
    # batch_date = datetime.now(timezone.utc)

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

    # fetch enrollments for current section (Target Summer 2025)
    unterview_enrollments = get_unterview_enrollments()

    # update documents with Canvas information
    patch_applicants_with_unterview(
        application_documents,
        unterview_enrollments,
    )

    # respond with success, number of updated documents, batch date
    return {"success": True, "path": users_csv}
