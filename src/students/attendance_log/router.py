from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, status, BackgroundTasks
from sqlalchemy.orm import Session

from src.database.postgres.core import make_session
from src.students.attendance_log.service import process_attendance

router = APIRouter()

@router.post("", status_code=status.HTTP_200_OK)
def process_attendance_log(
    background_tasks: BackgroundTasks,
    db: Session = Depends(make_session),
) -> Dict[str, Any]:
    """
    Main endpoint: calls service logic to process attendance logs.
    We let the service handle errors on a per-row basis.
    Always return { status=200, sheets_processed, sheets_failed }.
    """
    result = process_attendance(db, background_tasks)
    return result
