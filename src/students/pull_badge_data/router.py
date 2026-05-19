from typing import Any, Dict

from fastapi import APIRouter, Depends, status
from pymongo.database import Database
from sqlalchemy.orm import Session

from src.database.mongo.core import get_mongo
from src.database.postgres.core import make_session
from src.students.pull_badge_data.service import pull_badge_data
from src.utils.exceptions import handle_db_exceptions

router = APIRouter()

@router.post("", status_code=status.HTTP_200_OK)
def sync_badge_data(
    mongo: Database = Depends(get_mongo),
    db: Session = Depends(make_session),
) -> Dict[str, Any]:
    """
    Pull badge data from Parchment and sync into MongoDB.

    Fetches all badge classes from Parchment, upserts them into the
    badges collection, and creates or updates StudentBadge records
    for students enrolled in linked Canvas courses.
    """
    try:
        result = pull_badge_data(mongo=mongo, db=db)
        return result
    except Exception as exc:
        handle_db_exceptions(db, exc)