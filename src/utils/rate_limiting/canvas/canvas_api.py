"""
Canvas API Client with rate limiting.

Uses requests ratelimiter which uses leaky bucket algorithm (same as Canvas)
that automatically delays requests to stay within rate limits.

Canvas Rate Limits:
   - 700 unit quota, refills at 10 units/second
   - Returns 403 "Rate Limit Exceeded" or 429 when exceeded
"""

import time
from typing import Optional
from requests import Response
from requests_ratelimiter import LimiterSession
from src.config import settings

class CanvasRateLimitError(Exception):
    """Raised when Canvas API rate limit is exceeded after retries."""
    pass


class CanvasClient:
    """Rate-limited client for Canvas API requests."""
    
    def __init__( self, base_url: Optional[str] = None, access_token: Optional[str] = None, max_retries: int = 3):
        self.base_url = (base_url or settings.canvas_api_test_url).rstrip("/")
        self.access_token = access_token or settings.cti_access_token
        self.max_retries = max_retries
        self.session = LimiterSession(per_second=settings.canvas_rate_limit_per_second)
    
    def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
        data: Optional[dict] = None,
        timeout: int = 10,
    ) -> Response:
        """Make a rate-limited request to Canvas API with automatic retry on rate limit errors."""
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
            
            if not self.is_rate_limited(response):
                return response
            
            if attempt < self.max_retries:
                time.sleep(2 ** attempt)
        
        raise CanvasRateLimitError(
            f"Rate limit exceeded after {self.max_retries} retries: {response.text}"
        )
    
    def get(self, endpoint: str, params: Optional[dict] = None) -> Response:
        """GET request to Canvas API."""
        return self.request("GET", endpoint, params=params)
    
    def post(self, endpoint: str, json: Optional[dict] = None, data: Optional[dict] = None) -> Response:
        """POST request to Canvas API."""
        return self.request("POST", endpoint, json=json, data=data)
    
    def put(self, endpoint: str, json: Optional[dict] = None, data: Optional[dict] = None) -> Response:
        """PUT request to Canvas API."""
        return self.request("PUT", endpoint, json=json, data=data)
    
    def delete(self, endpoint: str) -> Response:
        """DELETE request to Canvas API."""
        return self.request("DELETE", endpoint)
    
    def build_url(self, endpoint: str) -> str:
        """Build full URL from endpoint"""
        if endpoint.startswith(("http://", "https://")):
            return endpoint
        endpoint = endpoint.lstrip("/")
        return f"{self.base_url}/api/v1/{endpoint}"
    
    def is_rate_limited(self, response: Response) -> bool:
        """Check if response indicates rate limiting."""
        if response.status_code == 429:
            return True
        if response.status_code == 403 and "Rate Limit Exceeded" in response.text:
            return True
        return False


# Default client instance
canvas_client = CanvasClient()