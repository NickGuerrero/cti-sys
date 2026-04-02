"""
Minor stress test for Parchment Digital Badges API rate limiting.

Run test:

    python rate_limit_testing/parchment_minor_stress_testing.py

"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.utils.rate_limiting.parchment_badges.parchment_api import ParchmentClient
import time

REQUEST_COUNT = 25

client = ParchmentClient()

# Test basic request works
response = client.get("v2/users/self")
data = response.json().get("result", [{}])[0]

print(f"Status: {response.status_code}")
print(f"Name: {data.get('firstName')} {data.get('lastName')}")
print(f"Email: {data.get('emails', [{}])[0].get('email')}")
print(f"Badgr Domain: {data.get('badgrDomain')}\n")

# Test read access to issuers
response = client.get("v2/issuers")
issuers = response.json().get("result", [])
print(f"Issuers ({response.status_code}): {len(issuers)} found")
for issuer in issuers:
    print(f"  - {issuer.get('name')} ({issuer.get('entityId')})")
print()

# Test read access to badge classes
response = client.get("v2/badgeclasses")
badgeclasses = response.json().get("result", [])
print(f"Badge Classes ({response.status_code}): {len(badgeclasses)} found")
for badge in badgeclasses:
    print(f"  - {badge.get('name')} ({badge.get('entityId')})")
print()

# Test rate limiting is active
print(f"Sending {REQUEST_COUNT} requests:")
start = time.time()
for i in range(REQUEST_COUNT):
    client.get("v2/users/self")
    elapsed = time.time() - start
    print(f"Request {i + 1}/{REQUEST_COUNT} - {elapsed:.2f}s")

total = time.time() - start
rate = REQUEST_COUNT / total
print(f"\n{REQUEST_COUNT} requests in {total:.2f}s ({rate:.1f} requests/sec)")