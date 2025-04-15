from fastapi import APIRouter, Depends, status
from pymongo.database import Database

from src.applications.canvas_export.schemas import CanvasExportResponse
from src.applications.canvas_export.service import add_applicants_to_canvas
from src.database.mongo.core import get_mongo

router = APIRouter()

@router.post(
    "",
    description="Exports a batch of Accelerate program applicants to Canvas.",
    response_description="Added applicants to Canvas and Unterview course",
    status_code=status.HTTP_200_OK,
    response_model=CanvasExportResponse
)
def export_applicants_to_canvas(
    db: Database = Depends(get_mongo)
):
    return add_applicants_to_canvas(db=db)
