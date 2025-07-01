from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.database.postgres.core import make_session
from src.students.check_activity.service import process_student_activity
from src.students.check_activity.schemas import CheckActivityRequest, CheckActivityResponse

router = APIRouter()

@router.post("", response_model=CheckActivityResponse)
def check_activity(
    request: CheckActivityRequest,
    program: str = Query(..., description="The associated program."),
    db: Session = Depends(make_session),
):
    if not request.active_start:
        request.active_start = datetime.now() - timedelta(weeks=2)

    try:
        process_student_activity(request, program, db)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return CheckActivityResponse(status=200)