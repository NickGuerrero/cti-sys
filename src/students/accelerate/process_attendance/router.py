from typing import Dict

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from src.database.postgres.core import make_session
from src.students.accelerate.process_attendance.service import process_accelerate_metrics
from src.utils.exceptions import handle_db_exceptions 

router = APIRouter()

@router.post("", status_code=status.HTTP_200_OK)
def process_accelerate_attendance(db: Session = Depends(make_session)) -> Dict[str, int]:
    """
    Main endpoint: Process student_attendance into Accelerate level participation metrics
    and write results into the accelerate table for all active students.

    Always return { status = 200, records_updated = int}.
    On failure rolls back the transaction and send an HTTP-500 error.
    """
    # return process_accelerate_metrics(db)
    try:
        print("Test starting")
        return process_accelerate_metrics(db)
    except Exception as e:
        handle_db_exceptions(db, e)