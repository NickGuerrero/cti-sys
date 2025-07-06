from datetime import datetime
from typing import List, Tuple
from fastapi import HTTPException
from pydantic import ValidationError
from pymongo import UpdateOne
from pymongo.collection import Collection
from pymongo.client_session import ClientSession as MongoSession
from pymongo.database import Database as MongoDatabase
from requests import get
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.applications.canvas_export.utils import get_canvas_access_token
from src.applications.master_roster.models import ApplicationWithMasterProps
from src.applications.master_roster.schemas import MasterRosterCreateResponse, QuizSubmission
from src.config import ACCELERATE_FLEX_COLLECTION, APPLICATIONS_COLLECTION, settings
from src.database.postgres.models import Accelerate, CanvasID, Ethnicity, Student, StudentEmail
from src.reports.accelerate_flex.models import AccelerateFlexBase

def create_master_roster_records(
    mongo_db: MongoDatabase,
    mongo_session: MongoSession,
    postgres_session: Session
) -> MasterRosterCreateResponse:
    """
    Entry function for adding applicants to Master Roster.

    Applicant batch is based on students having submitted the Commitment Quiz. Applicant data is
    validated, records are added to PostgreSQL, and flex attributes are saved to the Accelerate
    Flex MongoDB collection.
    """
    mongo_session.start_transaction()

    submission_user_ids = get_all_quiz_submissions()

    application_collection = mongo_db.get_collection(APPLICATIONS_COLLECTION)

    applications_dict, invalid_applications_count = get_valid_applications(
        application_collection=application_collection,
        mongo_session=mongo_session,
        submission_user_ids=submission_user_ids
    )

    update_applicant_docs_commitment_status(
        application_collection=application_collection,
        mongo_session=mongo_session,
        applications_dict=applications_dict
    )

    duplicate_ids_count = remove_duplicate_applicants(
        applications_dict=applications_dict,
        postgres_session=postgres_session
    )

    add_all_students(
        applications_dict=applications_dict,
        postgres_session=postgres_session
    )

    create_applicant_flex_documents(
        applications_dict=applications_dict,
        mongo_db=mongo_db,
        mongo_session=mongo_session,
        postgres_session=postgres_session
    )
    
    updated_docs_count = update_applicant_docs_master_added(
        applications_dict=applications_dict,
        application_collection=application_collection,
        mongo_session=mongo_session,
        postgres_session=postgres_session
    )

    postgres_session.commit()
    mongo_session.commit_transaction()
    return MasterRosterCreateResponse(
        status=201,
        message=f"Successfully added {updated_docs_count} users to Master Roster [testing: found {len(submission_user_ids)} submissions]",
    )

def get_all_quiz_submissions() -> set[int]:
    """
    Function fetches user IDs from all Commitment Quiz QuizSubmissions on Canvas.

    Uses multiple external requests through pagination to fetch all submissions.
    """
    url = f"{settings.canvas_api_url}/api/v1/courses/{settings.course_id_101}/quizzes/{settings.commitment_quiz_id}/submissions?per_page=100"
    headers = {
        "Authorization": f"Bearer {get_canvas_access_token()}",
    }
    submission_user_ids = set()

    try:
        while url:
            response = get(url=url, headers=headers)
            response.raise_for_status()

            submissions = response.json()["quiz_submissions"]
            for submission in submissions:
                submission_user_ids.add(QuizSubmission(**submission).user_id)

            url = response.links.get("next", {}).get("url", None)

    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid quiz submission data found: {e.errors()}"
        )
    
    if not submission_user_ids:
        return MasterRosterCreateResponse(
            status=200,
            message="No commitment quiz submissions to process"
        )
    
    return submission_user_ids

def get_valid_applications(
    application_collection: Collection,
    mongo_session: MongoSession,
    submission_user_ids: set[int]
) -> Tuple[dict[int, ApplicationWithMasterProps], int]:
    """
    Function fetches Application collection documents from MongoDB.

    Result is a tuple with first index being a map of valid applications and second index
    containing the count of invalid documents found which met the DB filter criteria.

    `-> (dict, invalid_count)`
    """
    application_documents = application_collection.find({
        "$and": [
            {"canvas_id": {"$in": list(submission_user_ids)}},
            {"master_added": False}
        ]
    }, session=mongo_session)

    # validate the state of the application documents to be referenced
    applications_dict: dict[int, ApplicationWithMasterProps] = {}
    invalid_applications_count = 0
    for app_doc in application_documents:
        try:
            app = ApplicationWithMasterProps(**app_doc)
            applications_dict[app.canvas_id] = app
        except ValidationError as e:
            # NOTE log details when able
            invalid_applications_count += 1
    return (applications_dict, invalid_applications_count)

def update_applicant_docs_commitment_status(
    application_collection: Collection,
    mongo_session: MongoSession,
    applications_dict: dict[int, ApplicationWithMasterProps]
) -> None:
    """
    Function updates the Application collection documents acknowledging their
    addition to the Master Roster.

    MongoDB updates write based on bulk_write with `ordered=False`, meaning writes will continue
    despite encountered failures with reporting back (each update is independent).
    """
    if not applications_dict:
        raise HTTPException(
            status_code=422,
            detail=f"No applications match commitment user ids"
        )

    application_updates: List[UpdateOne] = []
    for user_canvas_id, _ in applications_dict.items():
        application_updates.append(
            UpdateOne(
                filter={"canvas_id": user_canvas_id},
                update={"$set": {
                    "commitment_quiz_completed": True
                }}
            )
        )
    update_result = application_collection.bulk_write(
        requests=application_updates,
        session=mongo_session,
        ordered=False
    )

    if not update_result.acknowledged:
        raise HTTPException(
            status_code=500,
            detail=f"Database failed to acknowledge bulk applications commitment update"
        )

def remove_duplicate_applicants(
    applications_dict: dict[int, ApplicationWithMasterProps],
    postgres_session: Session
) -> int:
    """
    Function pops applications that are found already inserted in the PostgreSQL database and
    returns the number of duplicates found.

    Raises error if no applications exist after filter (all commitments are of duplicate inserts).
    """
    # validate that the users have not committed already from PostreSQL -> else don't process again
    select_student_ids_stmt = (
        select(Student.cti_id)
        .where(Student.cti_id in list(applications_dict.keys()))
    )
    student_id_rows = postgres_session.execute(select_student_ids_stmt).fetchall()
    
    duplicate_ids_count = 0
    # each ID represents a duplicate that shouldn't be processed
    for student_id in student_id_rows:
        id = student_id.tuple()[0]
        applications_dict.pop(id)
        duplicate_ids_count += 1

    if len(applications_dict) == 0 and duplicate_ids_count > 0:
        raise HTTPException(
            status_code=422,
            detail=f"No new commitments, {duplicate_ids_count} duplicate requests"
        )

    return duplicate_ids_count

def application_to_student(application: ApplicationWithMasterProps) -> Student:
    student = Student(
        cti_id=application.canvas_id,
        fname=application.fname,
        pname=application.pname,
        lname=application.lname,
        target_year=get_target_year(application.app_submitted),
        gender=application.gender,
        first_gen=application.first_gen,
        institution=application.institution,
        birthday=application.birthday,
        ca_region=application.ca_region,
        email_addresses=[
            StudentEmail(
                email=application.email,
                cti_id=application.canvas_id,
                is_primary=True,
            )
        ],
        canvas_id=CanvasID(canvas_id=application.canvas_id, cti_id=application.canvas_id),
        ethnicities=[
            Ethnicity(
                cti_id=application.canvas_id,
                ethnicity=ethnicity,
            ) for ethnicity in application.race_ethnicity or []
        ],
        accelerate_record=Accelerate(
            cti_id=application.canvas_id,
            returning_student=application.returning,
        ),
    )
    return student

def get_target_year(date_applied: datetime) -> int:
    """
    Function returns the target summer's year for the applying student. Based on month
    application was recieved.

    Inclusively, applications from June (current year) through April (next year) have a target
    of next year. All other applicants should be targeted for the current year if admitted.
    """
    if date_applied.month >= 6: return date_applied.year + 1
    return date_applied

def application_to_flex(application: ApplicationWithMasterProps) -> AccelerateFlexBase:
    accelerate_flex = AccelerateFlexBase(
        cti_id=application.canvas_id,
        academic_goals=application.academic_goals,
        phone=application.phone,
        academic_year=application.academic_year,
        grad_year=application.grad_year,
        summers_left=application.summers_left,
        cs_exp=application.cs_exp,
        cs_courses=application.cs_courses,
        math_courses=application.math_courses,
        program_expectation=application.program_expectation,
        career_outlook=application.career_outlook,
        heard_about=application.heard_about
    )
    return accelerate_flex

def update_applicant_docs_master_added(
        applications_dict: dict[int, ApplicationWithMasterProps],
        application_collection: Collection,
        mongo_session: MongoSession,
        postgres_session: Session
):
    """
    Function updates the Application collection documents acknowledging their
    addition to the Master Roster.

    MongoDB updates write based on bulk_write with `ordered=False`, meaning writes will continue
    despite encountered failures with reporting back (each update is independent).
    """
    if not applications_dict:
        postgres_session.rollback()
        raise HTTPException(
            status_code=422,
            detail=f"No applications match commitment user ids"
        )

    application_updates: List[UpdateOne] = []
    for user_canvas_id, _ in applications_dict.items():
        application_updates.append(
            UpdateOne(
                filter={"canvas_id": user_canvas_id},
                update={"$set": {
                    "master_added": True
                }}
            )
        )

    update_result = application_collection.bulk_write(
        requests=application_updates,
        ordered=False,
        session=mongo_session
    )
    
    if not update_result.acknowledged:
        postgres_session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database failed to acknowledge bulk applications master_added update"
        )
    
    return update_result.modified_count

def add_all_students(
    applications_dict: dict[int, ApplicationWithMasterProps],
    postgres_session: Session
):
    """
    Function creates Student and relational entities from each application and inserts
    them into the PostgreSQL database. 

    If application data could not be validated as a Student or there is an insertion error,
    DB exception is thrown.
    """
    try:
        students = [application_to_student(app) for app in applications_dict.values()]
        postgres_session.add_all(students)
        postgres_session.flush()
    except SQLAlchemyError as e:
        postgres_session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"PostgreSQL Database error: {str(e)}"
        )

def create_applicant_flex_documents(
    applications_dict: dict[int, ApplicationWithMasterProps],
    mongo_db: MongoDatabase,
    mongo_session: MongoSession,
    postgres_session: Session
):
    """
    Function takes list of ApplicationWithMasterProps objects and inserts data into
    MongoDB Accelerate Flex collection.

    Insert will fail if ApplicationWithMasterProps attributes do not satisfy Accelerate Flex
    jsonSchema properties. Insert call uses `ordered=False` to skip insertion failures.
    """
    flex_model_dicts = [application_to_flex(app).model_dump() for app in applications_dict.values()]

    accelerate_flex_collection = mongo_db.get_collection(ACCELERATE_FLEX_COLLECTION)
    insert_result = accelerate_flex_collection.insert_many(
        documents=flex_model_dicts,
        ordered=False,
        session=mongo_session
    )
    if not insert_result.acknowledged:
        postgres_session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database failed to acknowledge flex inserts"
        )
