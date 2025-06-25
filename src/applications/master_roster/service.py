from typing import Any, List
from fastapi import HTTPException
from pydantic import ValidationError
from pymongo import UpdateOne
from pymongo.database import Database as MongoDatabase
from requests import get
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.applications.canvas_export.utils import get_canvas_access_token
from src.applications.master_roster.models import ApplicationWithMasterProps
from src.applications.master_roster.schemas import MasterRosterCreateRequest, MasterRosterCreateResponse, QuizSubmission
from src.config import ACCELERATE_FLEX_COLLECTION, APPLICATIONS_COLLECTION, settings
from src.database.postgres.models import Accelerate, CanvasID, Ethnicity, Student, StudentEmail
from src.reports.accelerate_flex.models import AccelerateFlexBase

def create_master_roster_records(
    master_roster_create_request: MasterRosterCreateRequest,
    mongo_db: MongoDatabase,
    postgres_session: Session
):
    # fetch QuizSubmissions from Canvas for Commitment Quiz (TODO w/ pagination)
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
    
    # fetch the applications for the newly committed students
    application_collection = mongo_db.get_collection(APPLICATIONS_COLLECTION)
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
            applications_dict[app.canvas_id] = app # NOTE technically possible for duplicates here
        except ValidationError as e:
            # NOTE log details when able
            invalid_applications_count += 1

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

    # add each remaining applications_dict value as a Student record TODO try wrap
    students: list[Student] = []
    for id, application in applications_dict.items():
        student = Student(
            cti_id=application.canvas_id,
            fname=application.fname,
            pname=application.pname,
            lname=application.lname,
            # 'join_date' default set by DB
            target_year=application.app_submitted.year, # FIXME change to base on month and year
            gender=application.gender,
            first_gen=application.first_gen,
            institution=application.institution,
            # 'is_graduate' default set
            birthday=application.birthday,
            # ca_region TODO this is missing from the DB, notes suggest not needed
            # 'active' default set
            # 'cohort_lc' default set
            # launch TODO this is missing from the DB, notes suggest not needed
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
                ) for ethnicity in application.race_ethnicity
            ],
            accelerate_record=Accelerate( # NOTE is this needed?
                cti_id=application.canvas_id,
                # 'student_type' default set
                # accountability_group
                # accountability_team
                # pathway_goal
                # 'participation_score' default set
                # 'sessions_attended' default set
                # 'participation_streak' default set
                returning_student=application.returning,
                # 'inactive_weeks' default set
                # 'active' default set
            ),
        )
        students.append(student)

    # NOTE all or nothing add + flush; duplicates search and data validation done above
    postgres_session.add_all(students)
    postgres_session.flush()

    flex_model_dicts: list[dict[str, Any]] = []
    for id, application in applications_dict.items():
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
        flex_model_dicts.append(accelerate_flex.model_dump())

    accelerate_flex_collection = mongo_db.get_collection(ACCELERATE_FLEX_COLLECTION)
    insert_result = accelerate_flex_collection.insert_many(flex_model_dicts)
    if not insert_result.acknowledged:
        postgres_session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database failed to acknowledge flex insert for user with cti_id {application.canvas_id}"
        )
    
    # update application documents to reflect a submitted commitment quiz
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
    
    if not application_collection.bulk_write(application_updates).acknowledged:
        # TODO do we need to require a sync with postgres_session.rollback() ?
        raise HTTPException(
            status_code=500,
            detail=f"Database failed to acknowledge bulk applications master_added update"
        )

    # if no errors occurred, commit the session transaction and respond with success status + message
    postgres_session.commit()
    return MasterRosterCreateResponse(
        status=201,
        message=f"Successfully added users to Master Roster" # TODO desc spec
    )
