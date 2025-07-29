# src/students/alternate_emails/router.py

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List, Optional
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.database.postgres.core import make_session
from src.students.alternate_emails.schemas import AlternateEmailRequest
from src.students.alternate_emails.service import modify, fetch_current_emails
from src.config import settings
from src.utils.email import send_email as raw_send_email

router = APIRouter()

def send_email_notification(
    to_email: str, 
    subject: str, 
    html_body: str
) -> None:
    """
    Wrap the real send_email so background-task failures never bubble up.
    This is used to send email notifications for alternate email changes.
    """
    try:
        raw_send_email(to_email, subject, html_body)
    except Exception:
        pass

def schedule_removal_notifications(
    background_tasks: BackgroundTasks,
    google_email: str,
    removed_emails: List[str]
) -> None:
    if not removed_emails:
        return
    removed_lower = [e.strip().lower() for e in removed_emails]
    html_list = ", ".join(removed_lower)
    background_tasks.add_task(
        send_email_notification,
        google_email,
        "Alternate email(s) removed",
        f"<p>You've removed the following alternate email(s): <b>{html_list}</b>.</p>"
    )

def schedule_alternate_notifications(
    background_tasks: BackgroundTasks,
    google_email: str,
    alt_emails: List[str]
) -> None:
    if not alt_emails:
        return
    alt_lower = [e.strip().lower() for e in alt_emails]
    html_list = ", ".join(alt_lower)
    background_tasks.add_task(
        send_email_notification,
        google_email,
        "New alternate email(s) added",
        f"<p>You've just added these alternate email(s): <b>{html_list}</b>.</p>"
    )

def schedule_primary_notifications(
    background_tasks: BackgroundTasks,
    old_primary: Optional[str],
    new_primary: Optional[str]
) -> None:
    if not new_primary:
        return
    if old_primary and old_primary != new_primary:
        background_tasks.add_task(
            send_email_notification,
            old_primary,
            "Your primary email was changed",
            f"<p>Your previous primary email ({old_primary}) was changed to {new_primary}.</p>"
        )
    background_tasks.add_task(
        send_email_notification,
        new_primary,
        "New primary email confirmed",
        f"<p>Your new primary email ({new_primary}) was confirmed.</p>"
    )

def schedule_combined_notifications(
    background_tasks: BackgroundTasks,
    google_email: str,
    removed_emails: List[str],
    alt_emails: List[str],
    old_primary: Optional[str],
    new_primary: Optional[str],
) -> None:
    """
    Schedule a single email summarizing all changes made to alternate emails.
    This combines removals, additions, and primary email changes into one message.
    """
    parts: List[str] = []

    if removed_emails:
        removed = ", ".join(e.strip().lower() for e in removed_emails)
        parts.append(f"You've removed these alternate email(s): <b>{removed}</b>")

    if alt_emails:
        added = ", ".join(e.strip().lower() for e in alt_emails)
        parts.append(f"You've added these alternate email(s): <b>{added}</b>")

    if new_primary:
        # summary line for everyone
        if old_primary and old_primary != new_primary:
            parts.append(f"Your primary address was changed from <b>{old_primary}</b> to <b>{new_primary}</b>")
        parts.append(f"Your new primary email <b>{new_primary}</b> has been confirmed")

    if parts:
        html_summary = f"""
        <html>
          <body style="font-family:Arial,sans-serif;line-height:1.5;">
            <p>Hi there,</p>
            <p>Here's a summary of your email updates:</p>
            <ul>
              {''.join(f'<li>{line}</li>' for line in parts)}
            </ul>
            <p>If you have any questions, contact support.</p>
            <p>Best,<br/>The CTI Team</p>
          </body>
        </html>
        """
        # send one combined email to the user who submitted the form
        background_tasks.add_task(
            send_email_notification,
            google_email,
            "Email address updates",
            html_summary
        )

    # send a dedicated message to the old primary email if it changed
    if new_primary and old_primary and old_primary != new_primary:
        html_old = f"""
        <html>
          <body style="font-family:Arial,sans-serif;line-height:1.5;">
            <p>Hi there,</p>
            <p>Your previous primary email <b>{old_primary}</b> was just changed to <b>{new_primary}</b>.</p>
            <p>If that wasn't you, please contact support immediately.</p>
            <p>Best,<br/>The CTI Team</p>
          </body>
        </html>
        """
        background_tasks.add_task(
            send_email_notification,
            old_primary,
            "Your primary email was changed",
            html_old
        )


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
        # google_email = request.google_form_email.strip().lower()
        # new_primary = request.primary_email.strip().lower() if request.primary_email else None
        # old_primary = google_email

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

    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")
