"""
Minor stress test for Canvas API rate limiting.

Run test:

    python rate_limit_testing/canvas_minor_stress_testing.py

"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.utils.rate_limiting.canvas.canvas_api import CanvasClient
from src.config import settings
import time

REQUEST_COUNT = 25

client = CanvasClient()

# Test basic request works
response = client.get("users/self")
print(f"Status: {response.status_code}")
print(f"User: {response.json().get('name')}\n")

# Test course enrollments
COURSE_ID = settings.course_id_101
print(f"Testing enrollments for course {COURSE_ID}:")
enrollments = client.get_course_enrollments(COURSE_ID)
print(f"Enrollments: {len(enrollments)} found")
for e in enrollments:
    print(f"  - {e.get('user', {}).get('name')} ({e.get('user_id')})")
print()

# Test bulk user progress
print(f"Testing bulk progress for course {COURSE_ID}:")
progress = client.get_bulk_user_progress(COURSE_ID)
print(f"Progress entries: {len(progress)} found")
for user_id, pct in progress.items():
    print(f"  - user_id={user_id} completion={pct}")
print()

# Test rate limiting is active
print(f"Sending {REQUEST_COUNT} requests:")
start = time.time()
for i in range(REQUEST_COUNT):
    client.get("users/self")
    elapsed = time.time() - start
    print(f"Request {i + 1}/{REQUEST_COUNT} - {elapsed:.2f}s")

total = time.time() - start
rate = REQUEST_COUNT / total
print(f"\n{REQUEST_COUNT} requests in {total:.2f}s ({rate:.1f} requests/sec)")