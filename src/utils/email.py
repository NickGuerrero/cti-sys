import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from src.config import settings

SENDGRID_API_KEY = settings.sendgrid_api_key
SENDER_EMAIL = settings.sendgrid_sender

def send_email(to_email: str, subject: str, html_content: str) -> None:
    client = SendGridAPIClient(SENDGRID_API_KEY)
    message = Mail(
        from_email=SENDER_EMAIL,
        to_emails=to_email,
        subject=subject,
        html_content=html_content,
    )
    client.send(message)
