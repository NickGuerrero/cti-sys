from typing import Any, Dict
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from src.database.postgres.core import make_session
from src.students.attendance_entry.schemas import AttendanceEntryRequest
from src.students.attendance_entry.service import process_session_submission
from src.utils.exceptions import handle_db_exceptions 

router = APIRouter()

@router.post("", status_code=status.HTTP_200_OK)
def process_attendance_entry(
    entry: AttendanceEntryRequest,
    db: Session = Depends(make_session),
) -> Dict[str, Any]:
    """
    Insert a single attendance session record.
    Authentication is enforced using the Authorization header:
        Authorization: Bearer <API_KEY>
    """
    try:
        return process_session_submission(db, entry)
    except Exception as e:
        handle_db_exceptions(db, e)