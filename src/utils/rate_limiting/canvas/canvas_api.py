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
    
    def __init__(self):
        if not settings.cti_access_token:
            raise ValueError("Missing CTI_ACCESS_TOKEN in environment")
        
        if settings.app_env == "production":
            self.base_url = settings.canvas_api_url
        else:
            self.base_url = settings.canvas_api_test_url

        self.access_token = settings.cti_access_token
        self.max_retries = settings.rate_limit_max_retries
        self.backoff_base = settings.rate_limit_backoff_base
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
                time.sleep(self.backoff_base ** attempt)
        
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
    
    def get_course_enrollments(self, canvas_id: int) -> list[dict]:
        """
        Fetch all active student enrollments for a Canvas course.

        Handles pagination automatically, collecting all enrolled students
        across all pages before returning. Only returns active enrollments
        with enrollment type 'student'.
        """
        endpoint = f"courses/{canvas_id}/enrollments"
        params = {
            "type[]": "StudentEnrollment",
            "state[]": "active",
            "per_page": 100,
        }
        enrollments = []

        while endpoint:
            response = self.get(endpoint, params=params)

            if response.status_code == 404:
                return []

            response.raise_for_status()
            enrollments.extend(response.json())

            # Canvas uses Link headers for pagination
            # next page URL is in response.links["next"]["url"] if it exists
            next_url = response.links.get("next", {}).get("url", None)

            if next_url:
                endpoint = next_url
                params = None
            else:
                endpoint = None

        return enrollments
    
    def get_bulk_user_progress(self, canvas_id: int) -> dict[int, float | None]:
        """
        Fetch module completion progress for all students in a Canvas course.
        Returns a dict mapping canvas user_id to completion percentage (0.0 - 1.0).
        """
        endpoint = f"courses/{canvas_id}/bulk_user_progress"
        progress_map = {}

        while endpoint:
            response = self.get(endpoint)

            if response.status_code == 404:
                return {}

            response.raise_for_status()

            for record in response.json():
                user_id = record.get("id")
                progress = record.get("progress", {})
                req_count = progress.get("requirement_count", 0)
                req_completed = progress.get("requirement_completed_count", 0)

                if req_count and req_count > 0:
                    progress_map[user_id] = round(req_completed / req_count, 4)
                else:
                    progress_map[user_id] = None

            next_url = response.links.get("next", {}).get("url", None)
            endpoint = next_url if next_url else None

        return progress_map

# Default client instance
canvas_client = CanvasClient()