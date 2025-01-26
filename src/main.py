from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from pymongo.database import Database

from src.app.models.mongo.models import ApplicationCreate
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
def test_mongo(db: Database = Depends(get_mongo)):
    try:
        return ping_mongo(db.client)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error accessing MongoDB: {str(e)}")
    
@app.post(
    "/applications",
    status_code=201,
    response_description="Application successfully inserted",
    description="Used for the creation of applications documents submitted to the program and saved for records",
)
def create_application(
    application: ApplicationCreate,
    db: Database = Depends(get_mongo),
):
    try:
        # validate that required model params are present
        validatedApp = ApplicationCreate.model_validate(application)

        # add extra form attributes from application body data
        validatedWithExtras = validatedApp.model_dump()
        extras = application.model_extra or {}
        for prop, value in extras.items():
            validatedWithExtras[prop] = value
        
        # insert the document with required and flexible form responses
        result = db.get_collection(APPLICATIONS_COLLECTION).insert_one(validatedWithExtras.copy())

        return {
            "applicationDict": validatedWithExtras,
            "_id": str(result.inserted_id)
        }
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"Invalid application fields received: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{str(e)}")
    