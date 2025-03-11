from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from pymongo.database import Database
from sqlalchemy import func

from src.config import APPLICATIONS_COLLECTION
from src.database.mongo.core import close_mongo, get_mongo, init_mongo, ping_mongo
from src.database.mongo.tmp_schemas import ApplicationCreate, ApplicationModel
from src.database.postgres.core import make_session
from src.database.postgres.models import AlternateEmailRequest, Student, StudentEmail
from src.database.postgres.tmp_schemas import StudentSchema

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup operations
    init_mongo()
    yield
    # on-shutdown operations
    await close_mongo()

app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_root():
    return {"message": "cti-sys v1.0.0"}

@app.get("/test-connection")
def confirm_conn(db: Session = Depends(make_session)):
    try:
        result = db.execute(text("SELECT 1"))
        if result.scalar() == 1:
            return {"message": "Database connection succeeded"}
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database Inaccessible")

@app.get("/test-db")
def database_test(db: Session = Depends(make_session)):
    try:
        exists = db.query(Student).first()
        if exists:
            # return StudentSchema.model_validate(Student)
            return StudentSchema.model_validate(exists)
        else:
            return {"message": "Database Accessible, but contains no data"}
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database Inaccessible")
    
@app.get("/test-mongo")
def mongo_test(db: Database = Depends(get_mongo)):
    try:
        ping_mongo(db.client)
        return {"message": "Successfully accessed MongoDB"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error accessing MongoDB: {str(e)}")
    
@app.post(
    "/api/applications",
    description="Creates a new application document for a unique prospective student.",
    response_description="Added a new application",
    status_code=status.HTTP_201_CREATED,
    response_model=ApplicationModel,
    responses={
        409: {
            "description": "Conflict: Duplicate key",
            "content": {
                "application/json": { "example": { "detail": "Duplicate index key value received" }}
            }
        },
    },
)
def create_application(
    application: ApplicationCreate,
    db: Database = Depends(get_mongo),
):
    try:
        application_collection = db.get_collection(APPLICATIONS_COLLECTION)

        # validate that required model params are present
        # Pydantic catches and raises its own code 422 on a failed Model.model_validate() call
        validated_app = ApplicationCreate.model_validate(application)

        # add extra form attributes from application body data
        validated_with_extras = validated_app.model_dump()
        extras = application.model_extra or {}
        for prop, value in extras.items():
            validated_with_extras[prop] = value
        
        # set time of application submission
        validated_with_extras["app_submitted"] = datetime.now(timezone.utc)

        # insert the document with required and flexible form responses
        app_result = application_collection.insert_one(validated_with_extras)

        created_app: ApplicationModel = application_collection.find_one({
            "_id": app_result.inserted_id
        })

        return created_app
    
    except DuplicateKeyError as e:
        raise HTTPException(status_code=409, detail=f"Duplicate index key value received: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{str(e)}")

@app.post("/api/students/alternate-emails", status_code=status.HTTP_200_OK)
def modify_alternate_emails(
    request: AlternateEmailRequest,
    db: Session = Depends(make_session),
):
    try:
        # Normalize all emails to lowercase and strip whitespace
        google_form_email = request.google_form_email.strip().lower()
        request_primary_email = request.primary_email.strip().lower() if request.primary_email else None
        request.alt_emails = [email.strip().lower() for email in request.alt_emails]
        request.remove_emails = [email.strip().lower() for email in request.remove_emails]

        # Find student by Google Form email
        student_email_entry = db.query(StudentEmail).filter(
            func.lower(StudentEmail.email) == google_form_email
        ).first()

        # Check if student was found
        if not student_email_entry:
            raise HTTPException(status_code=404, detail="Student not found")

        student = db.query(Student).filter(Student.cti_id == student_email_entry.cti_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")

        # Fetch all student emails and normalize to lowercase for comparisons
        student_emails = db.query(StudentEmail).filter(StudentEmail.cti_id == student.cti_id).all()
        student_email_dict = {email.email.lower(): email for email in student_emails} 
        student_email_list = set(student_email_dict.keys())
        
        # Ensure primary email change authentication
        if request_primary_email:
            # If changing primary email, it must match the Google form email
            if request_primary_email != google_form_email:
                raise HTTPException(
                    status_code=403,
                    detail="Primary email must match the email used to submit the form"
                )

        # Handle email removal
        for email_lower in request.remove_emails:
            if email_lower not in student_email_list:
                continue 

            # Prevent removal of primary email unless a new primary is specified
            if student_email_dict[email_lower].is_primary and not request_primary_email:
                raise HTTPException(
                    status_code=403,
                    detail=f"Cannot remove primary email: {email_lower} without specifying a new primary email"
                )

            # Delete the email
            db.query(StudentEmail).filter(
                StudentEmail.cti_id == student.cti_id,
                func.lower(StudentEmail.email) == email_lower
            ).delete()
            student_email_list.remove(email_lower)

        # Ensure new alternate emails do not belong to another student
        for email_lower in request.alt_emails:
            if email_lower in request.remove_emails:
                continue
                
            if email_lower not in student_email_list:
                # Check if email belongs to another student
                email_owner = db.query(StudentEmail).filter(
                    func.lower(StudentEmail.email) == email_lower
                ).first()
                
                if email_owner and email_owner.cti_id != student.cti_id:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Email '{email_lower}' is already associated with another student"
                    )
                    
                # Add new email
                new_email = StudentEmail(email=email_lower, cti_id=student.cti_id, is_primary=False)
                db.add(new_email)
                student_email_list.add(email_lower)

        # Handle primary email update
        if request_primary_email:
            db.query(StudentEmail).filter(StudentEmail.cti_id == student.cti_id).update({"is_primary": False})
            
            # Set the requested email as primary
            db.query(StudentEmail).filter(
                StudentEmail.cti_id == student.cti_id,
                func.lower(StudentEmail.email) == request_primary_email
            ).update({"is_primary": True})

        db.commit()
        return {"status": 200}
    
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except HTTPException as http_exc:
        db.rollback()
        raise http_exc
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    