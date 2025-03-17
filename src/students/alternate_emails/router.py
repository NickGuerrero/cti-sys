from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.database.postgres.core import make_session
from src.students.alternate_emails.schemas import AlternateEmailRequest
from src.students.alternate_emails.service import modify

router = APIRouter()

@router.post("", status_code=status.HTTP_200_OK)
def modify_alternate_emails(
    request: AlternateEmailRequest,
    db: Session = Depends(make_session),
):
    try:
        modify(request=request, db=db)
        return {"status": 200}
    
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except HTTPException as http_exc:
        db.rollback()
        raise http_exc
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
