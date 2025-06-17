from fastapi import APIRouter, Depends, status
from pymongo.database import Database
from sqlalchemy.orm import Session

from src.applications.master_roster.schemas import MasterRosterCreateRequest, MasterRosterCreateResponse
from src.applications.master_roster.service import create_master_roster_records
from src.database.mongo.core import get_mongo
from src.database.postgres.core import make_session

router = APIRouter()

@router.post(
    "",
    description="Creates required records for adding Accelerate student to the Master Roster.",
    response_description="Student added to the Master Roster",
    status_code=status.HTTP_201_CREATED,
    response_model=MasterRosterCreateResponse,
)
def add_student_to_master_roster(
    master_roster_create_request: MasterRosterCreateRequest,
    mongo_db: Database = Depends(get_mongo),
    postgres_session: Session = Depends(make_session)
):
    return create_master_roster_records(
        master_roster_create_request=master_roster_create_request,
        mongo_db=mongo_db,
        postgres_session=postgres_session,
    )
