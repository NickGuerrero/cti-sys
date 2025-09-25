from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.database.postgres.core import make_session
from src.students.alternate_emails.schemas import AlternateEmailRequest
from src.students.alternate_emails.service import modify, fetch_current_emails
from src.students.alternate_emails.notifications import schedule_combined_notifications
from src.config import settings
from src.utils.exceptions import handle_db_exceptions 

router = APIRouter()

@router.post("", status_code=status.HTTP_200_OK)
def modify_alternate_emails(
    request: AlternateEmailRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(make_session),
):
    """
    Modify a student's alternate and primary emails, then enqueue email notifications.
    """
    try:
        google_email = request.google_form_email.strip().lower()
        pre_update = fetch_current_emails(google_email, db=db)
        old_primary = pre_update["primary_email"]
        new_primary = request.primary_email.strip().lower() if request.primary_email else None

        modify(request=request, db=db)

        # Only one merged email per request
        schedule_combined_notifications(
            background_tasks,
            google_email,
            request.remove_emails,
            request.alt_emails,
            old_primary,
            new_primary,
        )

        # Fetch updated data for the response
        updated = fetch_current_emails(google_email, db=db)
        current_primary = updated["primary_email"]

        if settings.app_env == "production":
            return {"status": 200}
        return {
            "status": 200,
            "emails": updated["emails"],
            "primary_email": current_primary,
        }

    except Exception as e:
        handle_db_exceptions(db, e)
