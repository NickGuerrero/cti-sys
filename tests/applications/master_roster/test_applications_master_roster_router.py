from copy import deepcopy
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from pymongo.database import Database as MongoDatabase
import pytest

from src.main import app

client = TestClient(app)

class TestCanvasExport:
    @pytest.mark.integration
    def test_add_applicants_to_master_roster(self, real_mongo_db: MongoDatabase):
        """
        Integration test validating a successful internal API handling of route request for
        adding a batch of applicants to Canvas.

        External API (Canvas) is mocked and should be tested for successful connection elsewhere.
        """
        pass
        ex_quiz_submission = {
            "id": "123",
            "quiz_id": "456",
            "user_id": "789",
            "submission_id": "1011",
            "started_at": "2025-07-11T10:00:00Z",
            "finished_at": "2025-07-11T10:30:00Z",
            "end_at": "2025-07-11T11:00:00Z",
            "attempt": "1",
            "extra_attempts": "0",
            "extra_time": "5",
            "manually_unlocked": "true",
            "time_spent": "1800",
            "score": "95.5",
            "score_before_regrade": "90.0",
            "kept_score": "95.5",
            "fudge_points": "0.5",
            "has_seen_results": "true",
            "workflow_state": "complete",
            "overdue_and_needs_submission": "false"
        }
        
        user_1_submission = deepcopy(ex_quiz_submission)
        user_1_submission["user_id"] = 1
        user_2_submission = deepcopy(ex_quiz_submission)
        user_2_submission["user_id"] = 2
        first_page = MagicMock()
        first_page.json.return_value = {
            "quiz_submissions": [user_1_submission, user_2_submission]
        }
        first_page.links = {"next": {"url": "http://next-page.com"}}
        first_page.raise_for_status = lambda: None

        user_3_submission = deepcopy(ex_quiz_submission)
        user_3_submission["user_id"] = 3
        user_4_submission = deepcopy(ex_quiz_submission)
        user_4_submission["user_id"] = 4
        second_page = MagicMock()
        second_page.json.return_value = {
            "quiz_submissions": [user_3_submission, user_4_submission]
        }
        second_page.links = {"next": {"url": "http://last-page.com"}}
        second_page.raise_for_status = lambda: None

        user_5_submission = deepcopy(ex_quiz_submission)
        user_5_submission["user_id"] = 5
        third_page = MagicMock()
        third_page.json.return_value = {
            "quiz_submissions": [user_5_submission]
        }
        third_page.links = {}
        third_page.raise_for_status = lambda: None

        with patch("src.applications.master_roster.service.get", side_effect=[first_page, second_page, third_page]):
            pass