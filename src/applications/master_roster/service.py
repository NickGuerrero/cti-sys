from typing import List, Tuple
from fastapi import HTTPException
from pydantic import ValidationError
from pymongo import UpdateOne
from pymongo.collection import Collection
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
    postgres_session: Session
) -> MasterRosterCreateResponse:
    """
    Entry function for adding applicants to Master Roster.

    Applicant batch is based on students having submitted the Commitment Quiz. Applicant data is
    validated, records are added to PostgreSQL, and flex attributes are saved to the Accelerate
    Flex MongoDB collection.
    """
    user_submissions_dict = get_all_quiz_submissions()

    application_collection = mongo_db.get_collection(APPLICATIONS_COLLECTION)

    applications_dict, invalid_applications_count = get_valid_applications(
        application_collection=application_collection,
        user_submissions_dict=user_submissions_dict
    )

    update_applicant_docs_commitment_status(
        application_collection=application_collection,
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
        postgres_session=postgres_session
    )
    
    updated_docs_count = update_applicant_docs_master_added(
        applications_dict=applications_dict,
        application_collection=application_collection,
        postgres_session=postgres_session
    )

    postgres_session.commit()
    return MasterRosterCreateResponse(
        status=201,
        message=f"Successfully added {updated_docs_count} users to Master Roster",
    )

def get_all_quiz_submissions() -> dict[int, QuizSubmission]:
    """
    Function fetches Commitment Quiz QuizSubmissions from Canvas.

    Uses multiple external requests through pagination to fetch all submissions.
    """
    # TODO pagination
    url = f"{settings.canvas_api_url}/api/v1/courses/{settings.course_id_101}/quizzes/{settings.commitment_quiz_id}/submissions"
    headers = {
        "Authorization": f"Bearer {get_canvas_access_token()}",
    }

    response = get(url=url, headers=headers)
    response.raise_for_status()

    try:
        quiz_submissions_json = response.json()["quiz_submissions"]
        quiz_submissions: List[QuizSubmission] = [ # TODO pagination steps
            QuizSubmission(**submission) for submission in quiz_submissions_json
        ]
        user_submissions_dict = {submission.user_id: submission for submission in quiz_submissions}

    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid quiz submission data found: {e.errors()}"
        )
    
    if len(quiz_submissions) == 0:
        return MasterRosterCreateResponse(
            status=200,
            message="No commitment quiz submissions to process"
        )
    
    return user_submissions_dict

def get_valid_applications(
    application_collection: Collection,
    user_submissions_dict: dict[int, QuizSubmission]
) -> Tuple[dict[int, ApplicationWithMasterProps], int]:
    """
    Function fetches Application collection documents from MongoDB.

    Result is a tuple with first index being a map of valid applications and second index
    containing the count of invalid documents found which met the DB filter criteria.

    `-> (dict, invalid_count)`
    """
    application_documents = application_collection.find({
        "$and": [
            {"canvas_id": {"$in": list(user_submissions_dict.keys())}},
            {"master_added": False}
        ]
    })

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
    applications_dict: dict[int, ApplicationWithMasterProps]
) -> None:
    """
    Function updates the Application collection documents acknowledging their
    addition to the Master Roster.

    MongoDB updates write based on bulk_write with `ordered=False`, meaning writes will continue
    despite encountered failures with reporting back (each update is independent).
    """
    # update application documents to reflect a submitted commitment quiz
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
    
    if not application_collection.bulk_write(application_updates).acknowledged:
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
        target_year=application.app_submitted.year, # FIXME change to base on month and year
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
        postgres_session: Session
):
    """
    Function updates the Application collection documents acknowledging their
    addition to the Master Roster.

    MongoDB updates write based on bulk_write with `ordered=False`, meaning writes will continue
    despite encountered failures with reporting back (each update is independent).
    """
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

    update_result = application_collection.bulk_write(application_updates, ordered=False)
    
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
    insert_result = accelerate_flex_collection.insert_many(flex_model_dicts, ordered=False)
    if not insert_result.acknowledged:
        postgres_session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database failed to acknowledge flex inserts"
        )
