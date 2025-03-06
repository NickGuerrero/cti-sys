# Endpoint definitions
from fastapi import Depends, HTTPException, status, APIRouter
from pymongo.errors import DuplicateKeyError
from pymongo.database import Database

from .schemas import ApplicationCreate, ApplicationModel
from .service import create
from src.database.mongo.core import get_mongo

router = APIRouter()

@router.post(
    "",
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
        return create(application=application, db=db)
    
    except DuplicateKeyError as e:
        raise HTTPException(status_code=409, detail=f"Duplicate index key value received: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{str(e)}")
