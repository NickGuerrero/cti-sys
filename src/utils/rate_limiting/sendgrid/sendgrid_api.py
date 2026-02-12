"""
SendGrid API Client with rate limiting.

Uses pyrate limiter to enforce rate limits on SendGrid API calls.
It automatically delays requests to stay within rate limits.

SendGrid Rate Limits:
   - Default: 5 requests/second

"""

import time
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from pyrate_limiter import Duration, RequestRate, Limiter, BucketFullException
from python_http_client.exceptions import HTTPError
from src.config import settings


class SendGridRateLimitError(Exception):
    """Raised when SendGrid rate limit is exceeded."""
    pass


class SendGridClient:
    """Rate limited client for SendGrid API requests."""
    
    def __init__(
        self,
        api_key: str = None,
        sender_email: str = None,
        rate_per_second: int = None,
        retry_interval: float = 0.1,
        max_wait_seconds: float = 30.0,
        max_retries: int = 3,
        backoff_base: int = 2,
    ):
        self.api_key = api_key or settings.sendgrid_api_key
        self.sender_email = sender_email or settings.sendgrid_sender
        self.client = SendGridAPIClient(self.api_key)
        self.retry_interval = retry_interval
        self.max_wait_seconds = max_wait_seconds
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        rate = rate_per_second or settings.sendgrid_rate_limit_per_second
        self.limiter = Limiter(RequestRate(int(rate), Duration.SECOND))
    
    def acquire(self):
        """Acquire rate limit slot and waiting if necessary."""
        start_time = time.time()
        while True:
            try:
                self.limiter.try_acquire("sendgrid")
                return
            except BucketFullException:
                elapsed = time.time() - start_time
                if elapsed >= self.max_wait_seconds:
                    raise SendGridRateLimitError(
                        f"Timed out waiting for rate limit after {self.max_wait_seconds}s"
                    )
                time.sleep(self.retry_interval)
    
    def is_rate_limited(self, error: HTTPError) -> bool:
        """Check if error is a rate limit response."""
        return error.status_code == 429
    
    def send_email(self, to_email: str, subject: str, html_content: str) -> None:
        """Send a rate limited email via SendGrid with retry on rate limit errors."""
        message = Mail(
            from_email=self.sender_email,
            to_emails=to_email,
            subject=subject,
            html_content=html_content,
        )
        
        for attempt in range(self.max_retries + 1):
            self.acquire()
            try:
                self.client.send(message)
                return
            except HTTPError as e:
                if not self.is_rate_limited(e):
                    raise
                if attempt < self.max_retries:
                    time.sleep(self.backoff_base ** attempt)
        
        raise SendGridRateLimitError(
            f"Rate limit exceeded after {self.max_retries} retries"
        )


# Default client instance
sendgrid_client = SendGridClient()