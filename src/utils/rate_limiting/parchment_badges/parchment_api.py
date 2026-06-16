"""
Parchment Digital Badges API Client with rate limiting.

Uses requests ratelimiter which uses leaky bucket algorithm (same as Canvas)
that automatically delays requests to stay within rate limits.

Parchment Rate Limits:
    - No published limit found; defaulting to 10 requests/second to match Canvas.
    - Returns 429 when exceeded.

Authentication:
    - Access tokens expire after 24 hours, refresh token is used to renew.
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Iterator, Optional
import requests
from requests import Response
from requests_ratelimiter import LimiterSession
from src.config import settings


class ParchmentRateLimitError(Exception):
    """Raised when Parchment API rate limit is exceeded after retries."""
    pass


class ParchmentClient:
    """Rate-limited client for Parchment Digital Badges API requests."""

    def __init__(self):
        if not settings.parchment_email or not settings.parchment_password:
            raise ValueError(
                "Missing PARCHMENT_EMAIL or PARCHMENT_PASSWORD in environment"
            )

        self.base_url = settings.parchment_api_url
        self.token_url = f"{self.base_url}/o/token"
        self.max_retries = settings.rate_limit_max_retries
        self.backoff_base = settings.rate_limit_backoff_base
        self.session = LimiterSession(per_second=settings.parchment_rate_limit_per_second)

        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None

    
    # TOKEN MANAGEMENT METHODS 

    def is_token_valid(self) -> bool:
        """True if the current access token has not expired."""
        if not self.access_token or not self.token_expires_at:
            return False
        # Renew 60s early to avoid edge cases of token expiring during a request
        return datetime.now(timezone.utc) < (self.token_expires_at - timedelta(seconds=60))

    def store_token(self, data: dict) -> None:
        """Store access and refresh tokens along with expiration time."""
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        self.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])

    def authenticate(self) -> None:
        """Obtain a new access token via OAuth2 password grant."""
        response = requests.post(
            self.token_url,
            data={
                "username": settings.parchment_email,
                "password": settings.parchment_password,
            },
            timeout=10,
        )
        if response.status_code == 401:
            raise ValueError("Invalid PARCHMENT_EMAIL or PARCHMENT_PASSWORD")
        
        response.raise_for_status()
        self.store_token(response.json())

    def refresh_access_token(self) -> None:
        """Exchange the refresh token for a new access token."""
        response = requests.post(
            self.token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            },
            timeout=10,
        )
        if response.status_code == 401:
            # Refresh token has also expired, fall back to full re-authentication.
            self.authenticate()
            return
        response.raise_for_status()
        self.store_token(response.json())

    def ensure_authenticated(self) -> None:
        """Guarantee a valid access token before making an API call."""
        if self.is_token_valid():
            return
        if self.refresh_token:
            self.refresh_access_token()
        else:
            self.authenticate()


    # API REQUEST METHODS

    def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
        data: Optional[dict] = None,
        timeout: int = 10,
    ) -> Response:
        """Make a rate-limited request to the Parchment API with automatic retry on rate limit errors."""
        self.ensure_authenticated()
        url = self.build_url(endpoint)
        headers = {"Authorization": f"Bearer {self.access_token}"}

        for attempt in range(self.max_retries + 1):
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json,
                data=data,
                headers=headers,
                timeout=timeout,
            )

            if response.status_code == 401:
                headers = self.handle_unauthorized()
                continue

            if not self.is_rate_limited(response):
                return response

            if attempt < self.max_retries:
                time.sleep(self.backoff_base ** attempt)

        raise ParchmentRateLimitError(
            f"Rate limit exceeded after {self.max_retries} retries: {response.text}"
        )

    def get(self, endpoint: str, params: Optional[dict] = None) -> Response:
        """GET request to Parchment API."""
        return self.request("GET", endpoint, params=params)

    def post(self, endpoint: str, json: Optional[dict] = None, data: Optional[dict] = None) -> Response:
        """POST request to Parchment API."""
        return self.request("POST", endpoint, json=json, data=data)
    
    def put(self, endpoint: str, json: Optional[dict] = None, data: Optional[dict] = None) -> Response:
        """PUT request to Parchment API."""
        return self.request("PUT", endpoint, json=json, data=data)

    def delete(self, endpoint: str) -> Response:
        """DELETE request to Parchment API."""
        return self.request("DELETE", endpoint)

    def patch(self, endpoint: str, json: Optional[dict] = None, data: Optional[dict] = None) -> Response:
        """PATCH request to Parchment API."""
        return self.request("PATCH", endpoint, json=json, data=data)

    def build_url(self, endpoint: str) -> str:
        """Build full URL from endpoint"""
        if endpoint.startswith(("http://", "https://")):
            return endpoint
        endpoint = endpoint.lstrip("/")
        return f"{self.base_url}/{endpoint}"

    def is_rate_limited(self, response: Response) -> bool:
        """Check if the response indicates rate limiting."""
        return response.status_code == 429
    
    def handle_unauthorized(self) -> dict:
        """Handle 401 Unauthorized by clearing tokens and re-authenticating."""
        self.access_token = None
        self.ensure_authenticated()
        return {"Authorization": f"Bearer {self.access_token}"}
    
    def stream_badges(self) -> Iterator[list[dict]]:
        """
        Fetch badge classes from Parchment for CTI's issuer account, one page at a time.
        Yields lists of badge dicts until all pages have been fetched.
        """
        if not settings.parchment_issuer_id:
            raise ValueError("Missing PARCHMENT_ISSUER_ID in environment")

        endpoint = f"/v2/issuers/{settings.parchment_issuer_id}/badgeclasses"

        while endpoint:
            response = self.get(endpoint)
            response.raise_for_status()

            data = response.json()
            result = data.get("result", [])
            if result:
                yield result

            endpoint = data.get("nextPageUrl", None)