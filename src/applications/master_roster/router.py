from fastapi import APIRouter, Depends, status
from pymongo.client_session import ClientSession as MongoSession
from pymongo.database import Database
from sqlalchemy.orm import Session

from src.applications.master_roster.schemas import MasterRosterCreateResponse
from src.applications.master_roster.service import create_master_roster_records
from src.database.mongo.core import get_mongo, make_mongo_session
from src.database.postgres.core import make_session

router = APIRouter()

@router.post(
    "",
    description="Creates required records for adding Accelerate students to the Master Roster.",
    response_description="Students added to the Master Roster",
    status_code=status.HTTP_201_CREATED,
    response_model=MasterRosterCreateResponse,
)
def add_student_to_master_roster(
    mongo_db: Database = Depends(get_mongo),
    mongo_session: MongoSession = Depends(make_mongo_session),
    postgres_session: Session = Depends(make_session)
):
    return create_master_roster_records(
        mongo_db=mongo_db,
        mongo_session=mongo_session,
        postgres_session=postgres_session,
    )
