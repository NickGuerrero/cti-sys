from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from pymongo.database import Database

from src.app.models.mongo.models import ApplicationCreate, ApplicationModel
from src.config import APPLICATIONS_COLLECTION
from src.db_scripts.mongo import close_mongo, get_mongo, init_mongo , ping_mongo

from .app.database import make_session
from .app.models.postgres.models import Student
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
