from fastapi import HTTPException
from pydantic import ValidationError
from pymongo.database import Database as MongoDatabase
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.applications.master_roster.models import ApplicationWithMasterProps
from src.applications.master_roster.schemas import MasterRosterCreateRequest
from src.config import ACCELERATE_FLEX_COLLECTION, APPLICATIONS_COLLECTION
from src.database.postgres.models import Accelerate, CanvasID, Ethnicity, Student, StudentEmail
from src.reports.accelerate_flex.models import AccelerateFlexBase

def create_master_roster_records(
    master_roster_create_request: MasterRosterCreateRequest,
    mongo_db: MongoDatabase,
    postgres_session: Session
):
    # validate email exists in request -> else error (should be handled by request handler)
    applicant_email = master_roster_create_request.applicant_email

    # validate that the Application Collection document exists for this email -> else error
    application_collection = mongo_db.get_collection(APPLICATIONS_COLLECTION)
    applicant_document = application_collection.find_one({
        "email": applicant_email
    })
    if applicant_document is None:
        raise HTTPException(
            status_code=404,
            detail=f"User with email {applicant_email} not found"
        )

    # validate that the Application Collection document has required fields -> else error
    try:
        application = ApplicationWithMasterProps.model_validate(applicant_document)
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid application data provided: {e.errors()}"
        )

    # canvas_id known as is required in validated model definition
    applicant_canvas_id = application.canvas_id
    if applicant_canvas_id is None:
        raise HTTPException(
            status_code=422,
            detail=f"User with email {applicant_email} not enrolled in Canvas"
        )
    
    # update the Application Collection document to acknowledge quiz submission
    update_result = application_collection.update_one({"email": applicant_email}, {
        "$set": {"commitment_quiz_completed": True}
    })
    if not update_result.acknowledged:
        raise HTTPException(
            status_code=500,
            detail=f"Database failed to acknowledge update for user with email {applicant_email}"
        )

    # validate that the user has not committed already from PostreSQL -> else error
    select_student_stmt = (
        select(Student)
        .where(Student.cti_id == applicant_canvas_id)
    )
    student_row = postgres_session.execute(select_student_stmt).first()
    if student_row is not None:
        raise HTTPException(
            status_code=409,
            detail=f"User with Canvas ID {applicant_canvas_id} already added to Master Roster"
        )

    # add records to tables...
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
    postgres_session.add(student)
    postgres_session.flush()

    # TODO confirm not writing deep work, pathway, etc
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
    accelerate_flex_collection = mongo_db.get_collection(ACCELERATE_FLEX_COLLECTION)
    insert_result = accelerate_flex_collection.insert_one(accelerate_flex.model_dump())
    if not insert_result.acknowledged:
        postgres_session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database failed to acknowledge flex insert for user with cti_id {application.canvas_id}"
        )

    # if no errors occurred, commit the session transaction and respond with success status + message
    postgres_session.commit()

    # if there were errors, rollback the transaction
    pass
