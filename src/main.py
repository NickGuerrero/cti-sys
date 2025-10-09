from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from pymongo.database import Database

from src.api import api_router
from src.database.mongo.core import close_mongo, get_mongo, init_mongo, ping_mongo
from src.database.postgres.core import make_session
from src.database.postgres.models import Student
from src.students.models import StudentDTO
from src.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup operations
    init_mongo()
    yield
    # on-shutdown operations
    await close_mongo()

if settings.app_env == "production":
    # In production: disable Swagger UI and /docs endpoints
    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
else:
    # In development: keep docs enabled
    app = FastAPI(lifespan=lifespan)

if settings.app_env != "production":
    @app.get("/", tags=["Health"])
    def read_root():
        return {"message": "cti-sys v1.0.0"}

    @app.get("/test-connection", tags=["Health"])
    def confirm_conn(db: Session = Depends(make_session)):
        try:
            result = db.execute(text("SELECT 1"))
            if result.scalar() == 1:
                return {"message": "Database connection succeeded"}
        except SQLAlchemyError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database inaccessible",
            )

    @app.get("/test-db", tags=["Health"])
    def database_test(db: Session = Depends(make_session)):
        try:
            exists = db.query(Student).first()
            if exists:
                return StudentDTO.model_validate(exists)
            return {"message": "Database accessible, but contains no data"}
        except SQLAlchemyError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database inaccessible",
            )

    @app.get("/test-mongo", tags=["Health"])
    def mongo_test(db: Database = Depends(get_mongo)):
        try:
            ping_mongo(db.client)
            return {"message": "Successfully accessed MongoDB"}
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error accessing MongoDB: {str(e)}",
            )
        
app.include_router(api_router, prefix="/api")
