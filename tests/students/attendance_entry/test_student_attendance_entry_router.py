import pytest
from unittest.mock import MagicMock
from gspread_dataframe import set_with_dataframe
import pandas as pd
from src.config import settings
from src.students.attendance_entry import service as entry_service
from src.gsheet.utils import create_credentials

class TestAttendanceEntry:
    @pytest.mark.integration
    @pytest.mark.gsheet
    def test_gsheet_whitelist_fetch(self):
        """ Test whitelist is fetch correctly, uses Test Worksheet """
        # Create set of emails for testing sheet fetching functionality
        # I'm adding my work email to make testing easier post-test calls
        email_write = ["nicguerrero@csumb.edu", "example2@email.com", "example3@email.com"]
        email_write.extend([""] * 50) # Clear any lingering emails from sheet
        # Set sheet values on sa_whitelist worksheet in the Test Spreadsheet
        df = pd.DataFrame({
            "email": email_write
        })
        gc = create_credentials()
        sh = gc.open_by_key(settings.test_sheet_key)
        whitelist = sh.worksheet(settings.sa_whitelist)
        set_with_dataframe(whitelist, df)
        # Verify email list is fetched correctly
        email_cache = entry_service.load_email_whitelist(settings.test_sheet_key, settings.sa_whitelist)
        assert len(email_cache) == 3
        assert "nicguerrero@csumb.edu" in email_cache
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
        client,
        session_date,
        start_time,
        end_time,
        monkeypatch,
        mock_postgresql_db,
    ):
        """ Test successful creation of attendance entry """

        # Mock whitelist call, different for each test
        monkeypatch.setattr(
            "src.students.attendance_entry.service.load_email_whitelist",
            MagicMock(return_value={"erfanarsala831@gmail.com"})
        )

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
        resp = client.post("/api/students/create-attendance-entry", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == 200
        assert data["session_id"] == 42
        assert data["owner"] == payload["owner"]
        assert data["link"] == payload["link"]

        mock_postgresql_db.add.assert_called_once()
        mock_postgresql_db.commit.assert_called_once()
        mock_postgresql_db.refresh.assert_called_once()

    @pytest.mark.parametrize("token,expected_status", [
        ("TEST_KEY", 200), # valid key
        ("WRONG_KEY", 401), # invalid key
        (None, 403), # missing key
    ])
    def test_api_key_cases(self, client, monkeypatch, mock_postgresql_db, token, expected_status):
        """ Test request with valid, invalid, and missing API keys """
        monkeypatch.setattr(
            "src.students.attendance_entry.service.load_email_whitelist",
            MagicMock(return_value={"x@ex.com"})
        )

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

        orig_headers = client.headers.copy()
        if token is None:
            client.headers.pop("Authorization", None)
        else:
            client.headers["Authorization"] = f"Bearer {token}"

        resp = client.post("/api/students/create-attendance-entry", json=payload)
        client.headers = orig_headers

        assert resp.status_code == expected_status
        if expected_status == 401:
            assert "Invalid or missing API key" in resp.text

    def test_not_in_allow_list(self, client, monkeypatch, mock_postgresql_db):
        """ Test request with email not in allow-list of emails from google sheet """
        monkeypatch.setattr(
            "src.students.attendance_entry.service.load_email_whitelist",
            MagicMock(return_value={"allowed@ex.com"})
        )

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
        resp = client.post("/api/students/create-attendance-entry", json=payload)
        assert resp.status_code == 403
        assert "Email not authorized" in resp.text

    def test_end_before_start(self, client, monkeypatch, mock_postgresql_db):
        """ Test request where session end time is before start time """
        monkeypatch.setattr(
            "src.students.attendance_entry.service.load_email_whitelist",
            MagicMock(return_value={"ok@ex.com"})
        )

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
        resp = client.post("/api/students/create-attendance-entry", json=payload)
        assert resp.status_code == 400
        assert "must be after" in resp.text
