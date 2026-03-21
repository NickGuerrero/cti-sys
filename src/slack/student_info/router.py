from typing import Any, Dict

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.database.postgres.core import make_session
from src.slack.student_info.service import fetch_student_info
from src.utils.exceptions import handle_db_exceptions 

router = APIRouter()

@router.get("", status_code=status.HTTP_200_OK)
def fetch_student_information(
    user_email: str,
    db: Session = Depends(make_session),
) -> Dict[str, Any]:
    """
    Fetch student information from the database.
    """
    try:
        return fetch_student_info(db, user_email)
    except Exception as exc:
        handle_db_exceptions(db, exc)
