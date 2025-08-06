from typing import Any, Dict
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from src.config import settings
from src.database.postgres.core import make_session
from src.students.attendance_entry.schemas import AttendanceEntryRequest
from src.students.attendance_entry.service import process_session_submission

router = APIRouter()

@router.post("", status_code=status.HTTP_200_OK)
def process_attendance_entry(
    entry: AttendanceEntryRequest,
    db: Session = Depends(make_session),
) -> Dict[str, Any]:
    """
    Validate submitter email against public Google Sheet allow-list and insert attendance.
    """
    try:
        return process_session_submission(db, entry)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {str(exc)}")
