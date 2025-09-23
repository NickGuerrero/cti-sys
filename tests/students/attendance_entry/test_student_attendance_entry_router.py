import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from gspread_dataframe import get_as_dataframe, set_with_dataframe
import pandas as pd

from src.main import app
from src.config import settings
from src.database.postgres.models import Attendance
from src.students.attendance_entry import service as entry_service
from src.gsheet.refresh.service import create_credentials

client = TestClient(app)


class TestAttendanceEntry:

    @pytest.fixture(autouse=True)
    def override_settings(self, monkeypatch):
        """ Override settings for tests """
        monkeypatch.setattr("src.config.settings.cti_sys_admin_key", "TEST_KEY")

    @pytest.mark.integration
    @pytest.mark.gsheet
    def test_gsheet_whitelist_fetch(self):
        """ Test whitelist is fetch correctly, uses Test Worksheet """
        # Set sheet values on sa_whitelist worksheet in the Test Spreadsheet
        df = pd.DataFrame({
            "email": ["example1@email.com", "example2@email.com", "example3@email.com"]
        })
        gc = create_credentials()
        sh = gc.open_by_key(settings.test_sheet_key)
        whitelist = sh.worksheet(settings.sa_whitelist)
        set_with_dataframe(whitelist, df)
        # Verify email list is fetched correctly
        email_cache = entry_service.load_email_whitelist(settings.test_sheet_key, settings.sa_whitelist)
        assert len(email_cache) == 3
        assert "example1@email.com" in email_cache
        assert "example2@email.com" in email_cache
        assert "example3@email.com" in email_cache

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

        # Mock whitelist call, different for each test
        def mock_whitelist():
            return set(["erfanarsala831@gmail.com"])
        monkeypatch.setattr("src.students.attendance_entry.service.load_email_whitelist", mock_whitelist)

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
        headers = {"Authorization": "Bearer TEST_KEY"}

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

        def mock_whitelist():
            return set(["x@ex.com"])
        monkeypatch.setattr("src.students.attendance_entry.service.load_email_whitelist", mock_whitelist)

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
        headers = {"Authorization": "Bearer WRONG_KEY"}

        resp = client.post("/api/students/create-attendance-entry", json=payload, headers=headers)
        assert resp.status_code == 401
        assert "Invalid or missing API key" in resp.text

    def test_missing_api_key_header(self, monkeypatch, mock_postgresql_db):
        """ Test request missing the API key header """

        def mock_whitelist():
            return set(["x@ex.com"])
        monkeypatch.setattr("src.students.attendance_entry.service.load_email_whitelist", mock_whitelist)

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
        assert resp.status_code == 403

    def test_not_in_allow_list(self, monkeypatch, mock_postgresql_db):
        """ Test request with email not in allow-list of emails from google sheet """

        def mock_whitelist():
            return set(["allowed@ex.com"])
        monkeypatch.setattr("src.students.attendance_entry.service.load_email_whitelist", mock_whitelist)

        headers = {"Authorization": "Bearer TEST_KEY"}
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
        
        def mock_whitelist():
            return set(["ok@ex.com"])
        monkeypatch.setattr("src.students.attendance_entry.service.load_email_whitelist", mock_whitelist)

        headers = {"Authorization": "Bearer TEST_KEY"}
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
