from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.config import settings
from src.database.postgres.core import make_session
from src.database.postgres.models import MissingAttendance, StudentEmail
import src.students.missing_students.service as service

router = APIRouter()


@router.post("", status_code=status.HTTP_200_OK)
def recover_attendance(db: Session = Depends(make_session)) -> Dict[str, Any]:
    """
    Recover attendance for students with missing records.
    This endpoint processes MissingAttendance records and moves them to
    StudentAttendance if they do not already exist.
    Returns a summary of the operation.

    If app_env == production, return:
        {status: 200, moved: <count>}.
    Else, return:
        {status: 200, moved: <count>, rows: [{email, name, cti_id}]}
    """
    try:
        # Load all MissingAttendance records with their associated cti_id
        stmt = (
            select(MissingAttendance, StudentEmail.cti_id)
            .join(StudentEmail, MissingAttendance.email == StudentEmail.email)
        )
        matches: List[Tuple[MissingAttendance, int]] = db.execute(stmt).all()

        # If no matches, return early
        if not matches:
            return {"status": 200, "moved": 0}

        # Process matches to move records
        moved_rows = service.process_matches(db, matches)
        db.commit()
        count = len(moved_rows)

        # In production, we only return the count of moved records.
        # In development, we return the moved rows with email, name, and cti_id .
        if settings.app_env == "production":
            return {"status": 200, "moved": count}
        else:
            return {"status": 200, "moved": count, "rows": moved_rows}

    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
