"""
SendGrid API Client with rate limiting.

Uses pyrate limiter to enforce rate limits on gspread API calls.
It automatically delays requests to stay within rate limits.

SendGrid Rate Limits:
   - Default: 5 requests/second

"""

import time
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from pyrate_limiter import Duration, RequestRate, Limiter, BucketFullException
from src.config import settings

class SendGridRateLimitError(Exception):
    """Raised when SendGrid rate limit is exceeded."""
    pass


class SendGridClient:
    """Rate limited client for SendGrid API requests."""
    
    def __init__(self, api_key: str = None, sender_email: str = None, rate_per_second: float = None):
        self.api_key = api_key or settings.sendgrid_api_key
        self.sender_email = sender_email or settings.sendgrid_sender
        self.client = SendGridAPIClient(self.api_key)
        rate = rate_per_second or settings.sendgrid_rate_limit_per_second
        self.limiter = Limiter(RequestRate(int(rate), Duration.SECOND))
    
    def acquire(self):
        """Acquire rate limit slot, waiting if necessary."""
        while True:
            try:
                self.limiter.try_acquire("sendgrid")
                break
            except BucketFullException:
                time.sleep(0.1)
    
    def send_email(self, to_email: str, subject: str, html_content: str) -> None:
        """Send a rate limited email via SendGrid."""
        self.acquire()
        
        message = Mail(
            from_email=self.sender_email,
            to_emails=to_email,
            subject=subject,
            html_content=html_content,
        )
        self.client.send(message)


# Default client instance
sendgrid_client = SendGridClient()