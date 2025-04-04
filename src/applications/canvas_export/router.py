from fastapi import APIRouter, Depends, status
from pymongo.database import Database

from src.applications.canvas_export.service import add_applicants_to_canvas
from src.database.mongo.core import get_mongo

router = APIRouter()

@router.post("", status_code=status.HTTP_200_OK)
def export_applicants_to_canvas(
    db: Database = Depends(get_mongo)
):
    return add_applicants_to_canvas(db=db)
