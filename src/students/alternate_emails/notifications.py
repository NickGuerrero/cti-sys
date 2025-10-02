from typing import List, Optional
from fastapi import BackgroundTasks
from src.utils.email import send_email as raw_send_email

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
