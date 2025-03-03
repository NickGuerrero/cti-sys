from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Query
from pymongo.errors import DuplicateKeyError
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from pymongo.database import Database
from pydantic import BaseModel

from src.app.models.mongo.models import ApplicationCreate, ApplicationModel
from src.config import APPLICATIONS_COLLECTION
from src.db_scripts.mongo import close_mongo, get_mongo, init_mongo , ping_mongo

from .app.database import make_session
from src.app.models.postgres.models import Student, Attendance, StudentAttendance, AccelerateCourseProgress
from .app.models.postgres.schemas import StudentSchema

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
            return StudentSchema.model_validate(Student)
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

#Request body model
class CheckActivityRequest(BaseModel):
    target: str
    active_start: Optional[datetime] = None
    activity_thresholds: Dict[str, List[str]]

#Response model
class CheckActivityResponse(BaseModel):
    status: int

# Define the endpoint
@app.post("/api/students/check-activity", response_model=CheckActivityResponse)
def check_activity(
    request: CheckActivityRequest,
    program: str = Query(..., description="The associated program. Only 'accelerate' is supported at this time."),
    db: Session = Depends(make_session)
):
    if program != "accelerate":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported program")

    # Set default active_start to 2 weeks ago if not provided
    if not request.active_start:
        request.active_start = datetime.now() - timedelta(weeks=2)

    # Query the database to get the list of students based on the target
    if request.target == "active":
        students = db.query(Student).filter(Student.active == True).all()
    elif request.target == "inactive":
        students = db.query(Student).filter(Student.active == False).all()
    elif request.target == "both":
        students = db.query(Student).all()
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid target")

    # Check activity for each student
    for student in students:
        is_active = check_student_activity(student, request.active_start, request.activity_thresholds, db)
        student.active = is_active

    db.commit()

    return CheckActivityResponse(status=200)

def check_student_activity(student: Student, active_start: datetime, activity_thresholds: Dict[str, List[str]], db: Session) -> bool:
    # Check if the student attended any sessions after the active_start date
    attended_sessions = db.query(StudentAttendance).join(Attendance).filter(
        StudentAttendance.cti_id == student.cti_id,
        Attendance.session_start >= active_start,
        Attendance.session_type.in_(activity_thresholds.get("last_attended_session", []))
    ).count()

    # Check if the student completed any courses in the activity_thresholds
    completed_courses = db.query(AccelerateCourseProgress).filter(
        AccelerateCourseProgress.cti_id == student.cti_id,
        AccelerateCourseProgress.latest_course.in_(activity_thresholds.get("completed_courses", []))
    ).count()

    # Determine if the student is active based on the activity thresholds
    return attended_sessions > 0 or completed_courses > 0