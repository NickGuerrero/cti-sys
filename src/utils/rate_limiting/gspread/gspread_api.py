"""
Google Sheets API Client with rate limiting.

Uses pyrate limiter to enforce rate limits on gspread API calls.
It automatically delays requests to stay within rate limits.

Google Sheets Rate Limits:
   - 300 requests per minute per project
   - 60 requests per minute per user per project
   - Default: 5 request/second
"""

import gspread
import pandas
import time
from gspread.exceptions import APIError
from pyrate_limiter import Duration, RequestRate, Limiter, BucketFullException
from typing import Any, Dict, Optional

from src.config import settings
from src.gsheet.utils import create_credentials


class GoogleSheetsRateLimitError(Exception):
    """Raised when Google Sheets rate limit is exceeded."""
    pass


class GoogleSheetsClient:
    """Rate limited client for Google Sheets API requests."""
    
    def __init__(
        self,
        credentials_file: Optional[str] = None,
        rate_per_second: int = None,
        retry_interval: float = 0.1,
        max_wait_seconds: float = 30.0,
        max_retries: int = 3,
        backoff_base: int = 2,
    ):
        self.credentials_file = credentials_file
        self.gc = None
        self.retry_interval = retry_interval
        self.max_wait_seconds = max_wait_seconds
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        rate = rate_per_second or settings.google_rate_limit_per_second
        self.limiter = Limiter(RequestRate(int(max(rate, 1)), Duration.SECOND))
    
    def acquire(self):
        """Acquire rate limit slot, waiting if necessary."""
        start_time = time.time()
        while True:
            try:
                self.limiter.try_acquire("gsheets")
                return
            except BucketFullException:
                elapsed = time.time() - start_time
                if elapsed >= self.max_wait_seconds:
                    raise GoogleSheetsRateLimitError(
                        f"Timed out waiting for rate limit after {self.max_wait_seconds}s"
                    )
                time.sleep(self.retry_interval)
    
    def is_rate_limited(self, error: APIError) -> bool:
        """Check if error is a rate limit response."""
        return error.response.status_code == 429
    
    def request_with_retry(self, func, *args, **kwargs):
        """Execute a function with retry on rate limit errors."""
        for attempt in range(self.max_retries + 1):
            self.acquire()
            try:
                return func(*args, **kwargs)
            except APIError as e:
                if not self.is_rate_limited(e):
                    raise
                if attempt < self.max_retries:
                    time.sleep(self.backoff_base ** attempt)
        
        raise GoogleSheetsRateLimitError(
            f"Rate limit exceeded after {self.max_retries} retries"
        )
    
    def get_client(self) -> gspread.Client:
        """Get or create gspread client with credentials."""
        if self.gc is None:
            if self.credentials_file:
                self.gc = gspread.service_account(filename=self.credentials_file)
            else:
                self.gc = create_credentials()
        return self.gc
    
    def open_by_key(self, sheet_key: str) -> gspread.Spreadsheet:
        """Open a spreadsheet by key with rate limiting and retry."""
        return self.request_with_retry(self.get_client().open_by_key, sheet_key)
    
    def open_by_url(self, url: str) -> gspread.Spreadsheet:
        """Open a spreadsheet by URL with rate limiting and retry."""
        return self.request_with_retry(self.get_client().open_by_url, url)
    
    def write_to_sheet(
        self,
        data: pandas.DataFrame,
        worksheet_name: str,
        sheet_key: str,
    ) -> Dict[str, Any]:
        """Write a pandas dataframe to a Google Sheet with rate limiting and retry."""
        spreadsheet = self.request_with_retry(self.get_client().open_by_key, sheet_key)
        worksheet = self.request_with_retry(spreadsheet.worksheet, worksheet_name)
        self.request_with_retry(worksheet.update,[data.columns.values.tolist()] + data.values.tolist())
        
        return {
            "success": True,
            "worksheet_updated": worksheet_name,
            "rows_updated": len(data)
        }


# Default client instance (production - uses env vars)
gsheets_client = GoogleSheetsClient()