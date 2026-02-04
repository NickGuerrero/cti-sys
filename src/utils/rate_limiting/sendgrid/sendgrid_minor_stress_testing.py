"""
Minor stress test for SendGrid API rate limiting.

Run from project root:

    python -m src.utils.rate_limiting.sendgrid.sendgrid_minor_stress_testing

"""

from src.utils.rate_limiting.sendgrid.sendgrid_api import SendGridClient
from src.config import settings
import time

REQUEST_COUNT = 15
TEST_EMAIL = settings.sendgrid_sender

client = SendGridClient()

# Test basic request works
try:
    client.send_email(
        to_email=TEST_EMAIL,
        subject="Rate Limit Test - Basic",
        html_content="<p>This is a test email.</p>"
    )
    print(f"Status: Sent successfully")
    print(f"To: {TEST_EMAIL}\n")
except Exception as e:
    print(f"Error: {e}\n")
    exit(1)

# Test rate limiting is active
print(f"Sending {REQUEST_COUNT} emails:")
start = time.time()
for i in range(REQUEST_COUNT):
    client.send_email(
        to_email=TEST_EMAIL,
        subject=f"Rate Limit Test - {i + 1}/{REQUEST_COUNT}",
        html_content=f"<p>Test email {i + 1} of {REQUEST_COUNT}</p>"
    )
    elapsed = time.time() - start
    print(f"Email {i + 1}/{REQUEST_COUNT} - {elapsed:.2f}s")

total = time.time() - start
rate = REQUEST_COUNT / total
print(f"\n{REQUEST_COUNT} emails in {total:.2f}s ({rate:.1f} emails/sec)")