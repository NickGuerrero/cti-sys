from typing import Any, Dict, Annotated
from fastapi import APIRouter, Depends, status, HTTPException, Header
from sqlalchemy.orm import Session

from src.config import settings
from src.database.postgres.core import make_session
from src.students.attendance_entry.schemas import AttendanceEntryRequest
from src.students.attendance_entry.service import process_session_submission

router = APIRouter()

API_KEY_HEADER_NAME = "X-CTI-Attendance-Key"
APIKeyHeader = Annotated[str, Header(..., alias=API_KEY_HEADER_NAME)]

def verify_attendance_api_key(client_key: APIKeyHeader) -> None:
    """
    Required to supply a matching API key in the X-CTI-Attendance-Key header.
    Returns None on success; raises HTTP 401 on mismatch.
    """
    server_key = settings.attendance_api_key
    if not server_key:
        # Misconfiguration: the server wasn't given a key
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfigured: missing ATTENDANCE_API_KEY"
        )
    if client_key != server_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )
    
@router.post(
    "",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_attendance_api_key)],
)
def process_attendance_entry(
    entry: AttendanceEntryRequest,
    db: Session = Depends(make_session),
) -> Dict[str, Any]:
    """
    Insert a single attendance session record.
    Authentication is enforced by using the X-CTI-Attendance-Key header.
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