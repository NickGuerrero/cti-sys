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
from pyrate_limiter import Duration, RequestRate, Limiter, BucketFullException
from typing import Any, Dict, Optional

from src.config import settings


class GoogleSheetsRateLimitError(Exception):
    """Raised when Google Sheets rate limit is exceeded."""
    pass


class GoogleSheetsClient:
    """Rate limited client for Google Sheets API requests."""
    
    def __init__(self, credentials_file: Optional[str] = None, rate_per_second: float = None):
        self.credentials_file = credentials_file
        self.gc = None
        rate = rate_per_second or settings.google_rate_limit_per_second
        self.limiter = Limiter(RequestRate(int(max(rate, 1)), Duration.SECOND))
    
    def acquire(self):
        """Acquire rate limit slot, waiting if necessary."""
        while True:
            try:
                self.limiter.try_acquire("gsheets")
                break
            except BucketFullException:
                time.sleep(0.1)
    
    def get_client(self) -> gspread.Client:
        """Get or create gspread client with credentials."""
        if self.gc is None:
            if self.credentials_file:
                self.gc = gspread.service_account(filename=self.credentials_file)
            else:
                self.gc = self.create_credentials_from_env()
        return self.gc
    
    def create_credentials_from_env(self) -> gspread.Client:
        """Create gspread client from environment variables (production)."""
        credentials = {
            "type": "service_account",
            "project_id": settings.gs_project_id,
            "private_key_id": settings.gs_private_key_id,
            "private_key": settings.gs_private_key,
            "client_email": settings.gs_client_email,
            "client_id": settings.gs_client_id,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": settings.gs_509_cert_url,
            "universe_domain": "googleapis.com"
        }
        return gspread.service_account_from_dict(credentials)
    
    def open_by_key(self, sheet_key: str) -> gspread.Spreadsheet:
        """Open a spreadsheet by key with rate limiting."""
        self.acquire()
        return self.get_client().open_by_key(sheet_key)
    
    def open_by_url(self, url: str) -> gspread.Spreadsheet:
        """Open a spreadsheet by URL with rate limiting."""
        self.acquire()
        return self.get_client().open_by_url(url)
    
    def write_to_sheet(
        self,
        data: pandas.DataFrame,
        worksheet_name: str,
        sheet_key: str,
    ) -> Dict[str, Any]:
        """Write a pandas dataframe to a Google Sheet with rate limiting."""
        self.acquire()
        spreadsheet = self.get_client().open_by_key(sheet_key)
        
        self.acquire()
        worksheet = spreadsheet.worksheet(worksheet_name)
        
        self.acquire()
        worksheet.update([data.columns.values.tolist()] + data.values.tolist())
        
        return {
            "success": True,
            "worksheet_updated": worksheet_name,
            "rows_updated": len(data)
        }


# Default client instance (production - uses env vars)
gsheets_client = GoogleSheetsClient()