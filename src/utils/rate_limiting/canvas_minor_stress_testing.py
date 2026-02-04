"""
Minor stress test for Canvas API rate limiting.

Run from project root:

    python -m src.utils.rate_limiting.canvas_minor_stress_testing

"""

from src.utils.rate_limiting.canvas_api import CanvasClient
import time

REQUEST_COUNT = 25

client = CanvasClient()

# Test basic request works
response = client.get("users/self")
print(f"Status: {response.status_code}")
print(f"User: {response.json().get('name')}\n")

# Test rate limiting is active
print(f"Sending {REQUEST_COUNT} requests...")
start = time.time()
for i in range(REQUEST_COUNT):
    client.get("users/self")
    elapsed = time.time() - start
    print(f"Request {i + 1}/{REQUEST_COUNT} - {elapsed:.2f}s")

total = time.time() - start
rate = REQUEST_COUNT / total
print(f"\n{REQUEST_COUNT} requests in {total:.2f}s ({rate:.1f} requests/sec)")