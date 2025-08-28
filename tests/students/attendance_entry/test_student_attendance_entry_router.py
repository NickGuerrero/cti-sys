import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from src.main import app
from src.database.postgres.models import Attendance
from src.students.attendance_entry import service as entry_service

client = TestClient(app)


class TestAttendanceEntry:

    def setup_method(self):
        ''' Clear cache before each test '''
        
        try:
            entry_service.load_allowed_emails.cache_clear()
        except Exception:
            pass

    @pytest.fixture(autouse=True)
    def override_settings(self, monkeypatch):
        """ Override settings for tests """

        monkeypatch.setattr("src.config.settings.attendance_api_key", "TEST_KEY")
        monkeypatch.setattr(
            "src.config.settings.allowed_sas_sheet_url",
            "https://docs.google.com/spreadsheets/d/TEST_SHEET/edit?gid=0#gid=0",
        )

    def test_normalize_google_sheet_url(self):
        """ Test normalization of Google Sheets URLs """

        fn = entry_service.normalize_google_sheet_url

        url1 = "https://docs.google.com/spreadsheets/d/ABC/export?format=csv&gid=123"
        assert fn(url1) == url1

        url2 = "https://docs.google.com/spreadsheets/d/XYZ/edit?gid=456#gid=456"
        assert (
            fn(url2)
            == "https://docs.google.com/spreadsheets/d/XYZ/export?format=csv&gid=456"
        )

        other = "https://example.com/foo?bar=1"
        assert fn(other) == other

    @pytest.mark.parametrize(
        "session_date,start_time,end_time",
        [
            ("06/16/2024", "10:00 AM", "11:00 AM"),
            ("2024-06-16", "18:00", "20:00"),
            ("06-16-2024", "18:00:00", "20:00:00"),
        ],
    )
    def test_create_attendance_entry_success(
        self,
        session_date,
        start_time,
        end_time,
        monkeypatch,
        mock_postgresql_db,
    ):
        """ Test successful creation of attendance entry """

        # Inline mock response for allow-list
        class Response:
            status_code = 200
            def raise_for_status(self): pass
            @property
            def content(self):
                return b"email\nerfanarsala831@gmail.com\n"

        monkeypatch.setattr("requests.get", lambda *a, **k: Response())

        mock_postgresql_db.add.return_value = None
        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.refresh.side_effect = lambda obj: setattr(obj, "session_id", 42)

        payload = {
            "owner": "erfanarsala831@gmail.com",
            "program": "Accelerate",
            "session_type": "Guided",
            "session_date": session_date,
            "session_start_time": start_time,
            "session_end_time": end_time,
            "link_type": "PEARDECK",
            "link": "https://docs.google.com/spreadsheets/d/ABC/edit?gid=0#gid=0",
        }
        headers = {"X-CTI-Attendance-Key": "TEST_KEY"}

        resp = client.post("/api/students/create-attendance-entry", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == 200
        assert data["session_id"] == 42
        assert data["owner"] == payload["owner"]
        assert data["link"] == payload["link"]

        mock_postgresql_db.add.assert_called_once()
        mock_postgresql_db.commit.assert_called_once()
        mock_postgresql_db.refresh.assert_called_once()

    def test_invalid_api_key(self, monkeypatch, mock_postgresql_db):
        """ Test request with invalid API key """

        class Response:
            status_code = 200
            def raise_for_status(self): pass
            @property
            def content(self):
                return b"email\nx@ex.com\n"

        monkeypatch.setattr("requests.get", lambda *a, **k: Response())

        payload = {
            "owner": "x@ex.com",
            "program": "Accelerate",
            "session_type": "Guided",
            "session_date": "06/16/2024",
            "session_start_time": "10:00 AM",
            "session_end_time": "11:00 AM",
            "link_type": "PEARDECK",
            "link": "https://docs.google.com/spreadsheets/d/ABC/edit?gid=0#gid=0",
        }
        headers = {"X-CTI-Attendance-Key": "WRONG_KEY"}

        resp = client.post("/api/students/create-attendance-entry", json=payload, headers=headers)
        assert resp.status_code == 401
        assert "Invalid or missing API key" in resp.text

    def test_missing_api_key_header(self, monkeypatch, mock_postgresql_db):
        """ Test request missing the API key header """

        class Response:
            status_code = 200
            def raise_for_status(self): pass
            @property
            def content(self):
                return b"email\nx@ex.com\n"

        monkeypatch.setattr("requests.get", lambda *a, **k: Response())

        payload = {
            "owner": "x@ex.com",
            "program": "Accelerate",
            "session_type": "Guided",
            "session_date": "06/16/2024",
            "session_start_time": "10:00 AM",
            "session_end_time": "11:00 AM",
            "link_type": "PEARDECK",
            "link": "https://docs.google.com/spreadsheets/d/ABC/edit?gid=0#gid=0",
        }
        resp = client.post("/api/students/create-attendance-entry", json=payload)
        assert resp.status_code == 422

    def test_not_in_allow_list(self, monkeypatch, mock_postgresql_db):
        """ Test request with email not in allow-list of emails from google sheet """

        class Response:
            status_code = 200
            def raise_for_status(self): pass
            @property
            def content(self):
                return b"email\nallowed@ex.com\n"

        monkeypatch.setattr("requests.get", lambda *a, **k: Response())

        headers = {"X-CTI-Attendance-Key": "TEST_KEY"}
        payload = {
            "owner": "blocked@ex.com",
            "program": "Accelerate",
            "session_type": "Guided",
            "session_date": "06/16/2024",
            "session_start_time": "10:00 AM",
            "session_end_time": "11:00 AM",
            "link_type": "PEARDECK",
            "link": "https://docs.google.com/spreadsheets/d/ABC/edit?gid=0#gid=0",
        }
        resp = client.post("/api/students/create-attendance-entry", json=payload, headers=headers)
        assert resp.status_code == 403
        assert "Email not authorized" in resp.text

    def test_end_before_start(self, monkeypatch, mock_postgresql_db):
        """ Test request where session end time is before start time """
        
        class Response:
            status_code = 200
            def raise_for_status(self): pass
            @property
            def content(self):
                return b"email\nok@ex.com\n"

        monkeypatch.setattr("requests.get", lambda *a, **k: Response())

        headers = {"X-CTI-Attendance-Key": "TEST_KEY"}
        payload = {
            "owner": "ok@ex.com",
            "program": "Accelerate",
            "session_type": "Guided",
            "session_date": "06/16/2024",
            "session_start_time": "11:00 AM",
            "session_end_time": "10:00 AM",
            "link_type": "PEARDECK",
            "link": "https://docs.google.com/spreadsheets/d/ABC/edit?gid=0#gid=0",
        }
        resp = client.post("/api/students/create-attendance-entry", json=payload, headers=headers)
        assert resp.status_code == 400
        assert "must be after" in resp.text
