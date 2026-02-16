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
    
    def __init__(self):
        if not settings.sendgrid_api_key:
            raise ValueError("Missing SENDGRID_API_KEY in environment")
        if not settings.sendgrid_sender:
            raise ValueError("Missing SENDGRID_SENDER in environment")
    
        self.api_key = settings.sendgrid_api_key
        self.sender_email = settings.sendgrid_sender
        self.client = SendGridAPIClient(self.api_key)
        self.retry_interval = settings.rate_limit_retry_interval
        self.max_wait_seconds = settings.rate_limit_max_wait_seconds
        self.max_retries = settings.rate_limit_max_retries
        self.backoff_base = settings.rate_limit_backoff_base
        self.limiter = Limiter(RequestRate(max(settings.sendgrid_rate_limit_per_second, 1), Duration.SECOND))
        
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
    
    def request_with_retry(self, func, *args, **kwargs):
        """Retry on rate limit errors."""
        for attempt in range(self.max_retries + 1):
            self.acquire()
            try:
                return func(*args, **kwargs)
            except HTTPError as e:
                if not self.is_rate_limited(e):
                    raise
                if attempt < self.max_retries:
                    time.sleep(self.backoff_base ** attempt)
        
        raise SendGridRateLimitError(
            f"Rate limit exceeded after {self.max_retries} retries"
        )

    def send_email(self, to_email: str, subject: str, html_content: str) -> None:
        """Send a rate limited email via SendGrid with retry on rate limit errors."""
        message = Mail(
            from_email=self.sender_email,
            to_emails=to_email,
            subject=subject,
            html_content=html_content,
        )
        self.request_with_retry(self.client.send, message)

# Default client instance
sendgrid_client = SendGridClient()