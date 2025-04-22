from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.database.postgres.core import make_session
from src.students.alternate_emails.schemas import AlternateEmailRequest
from src.students.alternate_emails.service import modify, fetch_current_emails
from src.config import settings

router = APIRouter()

@router.post("", status_code=status.HTTP_200_OK)
def modify_alternate_emails(
    request: AlternateEmailRequest,
    db: Session = Depends(make_session),
):
    """
    Endpoint to modify a student's alternate emails.
    Processes the email modification request and returns a simple status for production,
    or detailed email data for development and testing environments.
    """
    try:
        # Execute the email modification logic.
        modify(request=request, db=db)

        # In production, return a basic status message.
        if settings.app_env == "production":
            return {"status": 200}
        else:
            # In non production environments, return detailed email data.
            updated = fetch_current_emails(request.google_form_email.lower(), db=db)
            return {
                "status": 200,
                "emails": updated["emails"],
                "primary_email": updated["primary_email"],
            }
    
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except HTTPException as http_exc:
        db.rollback()
        raise http_exc
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")