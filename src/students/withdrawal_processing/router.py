from typing import Any, Dict

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.database.postgres.core import make_session
from src.students.withdrawal_processing.service import process_withdrawal_form
from src.utils.exceptions import handle_db_exceptions

router = APIRouter()

@router.post("", status_code=status.HTTP_200_OK)
def process_withdrawal(
    email: str,
    db: Session = Depends(make_session),
) -> Dict[str, Any]:
    """
    Handle CTI Accelerate withdrawal submissions.

    Receives the student's email from the form submission
    and deactivates all related records (Student, Accelerate)
    by setting 'active=False'.
    """
    try:
        result = process_withdrawal_form(db, email)
        db.commit()
        return result
    except Exception as exc:
        handle_db_exceptions(db, exc)
