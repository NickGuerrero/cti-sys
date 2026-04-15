"""
Minor stress test for Google Sheets API rate limiting.

Run test:

    python rate_limit_testing/gspread_minor_stress_testing.py

"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.utils.rate_limiting.gspread.gspread_api import GoogleSheetsClient
from src.config import settings
import time

REQUEST_COUNT = 15
TEST_SHEET_KEY = settings.test_sheet_key
CREDENTIALS_FILE = "gspread_credentials.json"

client = GoogleSheetsClient(credentials_file=CREDENTIALS_FILE)

# Test basic request works
try:
    sheet = client.open_by_key(TEST_SHEET_KEY)
    print(f"Status: Opened successfully")
    print(f"Sheet: {sheet.title}\n")
except Exception as e:
    print(f"Error: {e}\n")
    exit(1)

# Test rate limiting is active
print(f"Sending {REQUEST_COUNT} requests:")
start = time.time()
for i in range(REQUEST_COUNT):
    client.open_by_key(TEST_SHEET_KEY)
    elapsed = time.time() - start
    print(f"Request {i + 1}/{REQUEST_COUNT} - {elapsed:.2f}s")

total = time.time() - start
rate = REQUEST_COUNT / total
print(f"\n{REQUEST_COUNT} requests in {total:.2f}s ({rate:.1f} requests/sec)")