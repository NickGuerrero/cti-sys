from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.database.postgres.core import make_session
from src.students.activity.service import process_student_activity
from src.students.activity.schemas import CheckActivityRequest, CheckActivityResponse

router = APIRouter()

@router.post("/check-activity", response_model=CheckActivityResponse)
def check_activity(
    request: CheckActivityRequest,
    program: str = Query(..., description="The associated program. Only 'accelerate' is supported at this time."),
    db: Session = Depends(make_session),
):
    if program != "accelerate":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported program",
        )

    if not request.active_start:
        request.active_start = datetime.now() - timedelta(weeks=2)

    try:
        process_student_activity(request, program, db)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return CheckActivityResponse(status=200)