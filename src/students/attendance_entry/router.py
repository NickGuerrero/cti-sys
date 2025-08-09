from typing import Any, Dict
from fastapi import APIRouter, Depends, status, HTTPException, Header
from sqlalchemy.orm import Session

from src.config import settings
from src.database.postgres.core import make_session
from src.students.attendance_entry.schemas import AttendanceEntryRequest
from src.students.attendance_entry.service import process_session_submission

router = APIRouter()

# Define the API-key dependency
def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> None:
    """
    Require callers to supply a matching API key in the X-API-Key header.
    """
    if x_api_key != settings.attendance_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key"
        )

# Apply it to the POST endpoint
@router.post(
    "",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)]
)
def process_attendance_entry(
    entry: AttendanceEntryRequest,
    db: Session = Depends(make_session),
) -> Dict[str, Any]:
    """
    Validate API Key, then submitter email against public Google Sheet allow-list,
    parse date/time, and insert attendance.
    """
    try:
        return process_session_submission(db, entry)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(exc)}"
        )
