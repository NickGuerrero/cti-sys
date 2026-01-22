from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from src.config import settings
from src.database.postgres.core import make_session
from src.utils.exceptions import handle_db_exceptions
import src.students.accelerate.check_activity.service as service

router = APIRouter()

@router.post("", status_code=status.HTTP_200_OK)
def check_all_students_activity(
    db: Session = Depends(make_session),
) -> Dict[str, Any]:
    """Check and update activity for all active Accelerate students."""
    try:
        att_threshold = settings.activity_attendance_threshold_weeks
        canvas_threshold = settings.activity_canvas_threshold_weeks
        
        results = service.check_all_students(db, att_threshold, canvas_threshold)
        
        if settings.app_env == "production":
            results.pop("details", None)
        
        return results
        
    except Exception as exc:
        handle_db_exceptions(db, exc)