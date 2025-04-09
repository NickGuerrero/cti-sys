import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from requests.exceptions import HTTPError

from src.main import app
from src.database.postgres.models import Attendance

client = TestClient(app)


class TestProcessAttendanceLog:

    @pytest.mark.parametrize(
        "csv_content, expected_processed, expected_failed",
        [
            # Valid CSV scenario.
            (
                """
                Name,Email,Slide 1,Slide 2
                Jane Doe,jane@example.com,Hello,World
                John Doe,john@example.com,Yes,No
                """,
                1,  # sheets_processed
                0,  # sheets_failed
            ),
            # Missing 'Name' column -> fail scenario.
            (
                """
                Email,Slide 1,Slide 2
                someone@example.com,Answer1,Answer2
                """,
                0,
                1
            )
        ]
    )
    def test_process_attendance_log_simple(
        self,
        csv_content,
        expected_processed,
        expected_failed,
        monkeypatch,
        mock_postgresql_db
    ):
        """
        Test processing of a single attendance row under two conditions:
        - A valid CSV with the required 'Name' column.
        - An invalid CSV missing the 'Name' column.

        The number of processed vs. failed sheets should match expectations,
        and commits/rollbacks should occur accordingly.
        """
        # Create a single Attendance row in the mock DB.
        attendance_row = Attendance(
            session_id=2,
            link_type="PEARDECK",
            link="https://docs.google.com/spreadsheets/d/FAKE_DOC_ID/edit?gid=0#gid=0",
            last_processed_date=None
        )

        # Mock the DB query to return our single attendance row above.
        query_mock = mock_postgresql_db.query.return_value
        filter_mock = query_mock.filter.return_value
        filter_mock_2 = filter_mock.filter.return_value
        filter_mock_2.all.return_value = [attendance_row]

        # Mock the DB commit and rollback methods.
        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.rollback.return_value = None

        # This is a mock of the requests.get() response.
        # It simulates a successful HTTP response with the CSV content.
        class MockResponse:
            status_code = 200

            def raise_for_status(self):
                pass

            @property
            def content(self):
                # Encode the multiline CSV string to bytes.
                return csv_content.encode("utf-8")

        # This function will replace requests.get, returning our MockResponse above.
        def mock_requests_get(url, *args, **kwargs):
            return MockResponse()

        monkeypatch.setattr("requests.get", mock_requests_get)

        # Call the endpoint to process the attendance log.
        response = client.post("/api/students/process-attendance-log")
        assert response.status_code == 200

        # Verify the JSON response against our expected success/failure counts.
        resp_json = response.json()
        assert resp_json["sheets_processed"] == expected_processed
        assert resp_json["sheets_failed"] == expected_failed

        # Confirm DB commit or rollback was called as needed.
        if expected_processed:
            mock_postgresql_db.commit.assert_called_once()
        if expected_failed:
            mock_postgresql_db.rollback.assert_called_once()

    def test_multiple_attendance_rows_partial_fail(self, monkeypatch, mock_postgresql_db):
        """
        Test a scenario with multiple attendance rows in the database:
        - 3 valid CSV links, each should process successfully.
        - 1 link with an invalid CSV that fails.

        Expected results:
        - sheets_processed = 3
        - sheets_failed = 1
        - commit called three times, rollback called once
        """
        # Build four Attendance objects, 3 valid and 1 invalid.
        row_success_1 = Attendance(
            session_id=10,
            link_type="PEARDECK",
            link="https://docs.google.com/spreadsheets/d/DOC_ID_success_1/edit?gid=0#gid=0",
            last_processed_date=None
        )
        row_success_2 = Attendance(
            session_id=11,
            link_type="PEARDECK",
            link="https://docs.google.com/spreadsheets/d/DOC_ID_success_2/edit?gid=0#gid=0",
            last_processed_date=None
        )
        row_success_3 = Attendance(
            session_id=12,
            link_type="PEARDECK",
            link="https://docs.google.com/spreadsheets/d/DOC_ID_success_3/edit?gid=0#gid=0",
            last_processed_date=None
        )
        row_fail = Attendance(
            session_id=13,
            link_type="PEARDECK",
            link="https://docs.google.com/spreadsheets/d/DOC_ID_fail/edit?gid=0#gid=0",
            last_processed_date=None
        )

        # Mock the DB to return these four rows.
        query_mock = mock_postgresql_db.query.return_value
        filter_mock = query_mock.filter.return_value
        filter_mock_2 = filter_mock.filter.return_value
        filter_mock_2.all.return_value = [row_success_1, row_success_2, row_success_3, row_fail]

        # Mock the DB commit and rollback methods.
        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.rollback.return_value = None

        # Map each doc ID to either valid or invalid CSV bytes.
        valid_csv = b"Name,Email,Slide\nOne Person,person@example.com,Yes"
        invalid_csv = b"Email,Slide\nsomeone@example.com,NoNameColumn"
        csv_map = {
            "DOC_ID_success_1": valid_csv,
            "DOC_ID_success_2": valid_csv,
            "DOC_ID_success_3": valid_csv,
            "DOC_ID_fail": invalid_csv
        }

        # Mock the requests.get() method to return different CSV content based on the URL.
        # This simulates the behavior of fetching different CSVs based on the doc ID in the URL.
        class MockResponse:
            def __init__(self, content):
                self._content = content
                self.status_code = 200

            def raise_for_status(self):
                pass

            @property
            def content(self):
                return self._content

        def mock_requests_get(url, *args, **kwargs):
            # Extract doc ID from the URL to decide which CSV to return.
            try:
                after_d = url.split("/d/")[1]
                doc_id = after_d.split("/")[0]
            except IndexError:
                doc_id = "UNKNOWN"
            return MockResponse(csv_map.get(doc_id, b""))

        monkeypatch.setattr("requests.get", mock_requests_get)

        # Call the endpoint to process all attendance rows.
        response = client.post("/api/students/process-attendance-log")
        assert response.status_code == 200
        resp_json = response.json()

        # Check overall summary: 3 succeeded, 1 failed.
        assert resp_json["sheets_processed"] == 3
        assert resp_json["sheets_failed"] == 1
        assert mock_postgresql_db.commit.call_count == 3
        assert mock_postgresql_db.rollback.call_count == 1

    def test_empty_csv_fails(self, monkeypatch, mock_postgresql_db):
        """
        Test that an empty CSV string leads to a failure.

        This should result in:
        - sheets_processed = 0
        - sheets_failed = 1
        - rollback is called
        """
        attendance_row = Attendance(
            session_id=5,
            link_type="PEARDECK",
            link="https://docs.google.com/spreadsheets/d/EMPTY_DOC_ID/edit?gid=0#gid=0",
            last_processed_date=None
        )

        # Mock DB query to return the single attendance row that references an empty CSV.
        query_mock = mock_postgresql_db.query.return_value
        filter_mock = query_mock.filter.return_value
        filter_mock_2 = filter_mock.filter.return_value
        filter_mock_2.all.return_value = [attendance_row]

        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.rollback.return_value = None

        # Mock a response that has empty content.
        class MockResponse:
            status_code = 200
            def raise_for_status(self):
                pass
            @property
            def content(self):
                return b""

        def mock_requests_get(url, *args, **kwargs):
            return MockResponse()

        monkeypatch.setattr("requests.get", mock_requests_get)

        response = client.post("/api/students/process-attendance-log")
        assert response.status_code == 200
        resp_json = response.json()
        # We expect zero processed, one failure.
        assert resp_json["sheets_processed"] == 0
        assert resp_json["sheets_failed"] == 1
        mock_postgresql_db.rollback.assert_called_once()

    def test_requests_error(self, monkeypatch, mock_postgresql_db):
        """
        Test that any HTTP-related error (e.g., 403) when fetching CSV
        results in a failure of that sheet.

        - sheets_processed = 0
        - sheets_failed = 1
        """
        attendance_row = Attendance(
            session_id=99,
            link_type="PEARDECK",
            link="https://docs.google.com/spreadsheets/d/PROTECTED_DOC/edit?gid=0",
            last_processed_date=None
        )

        query_mock = mock_postgresql_db.query.return_value
        filter_mock = query_mock.filter.return_value
        filter_mock_2 = filter_mock.filter.return_value
        filter_mock_2.all.return_value = [attendance_row]

        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.rollback.return_value = None

        # Simulate an HTTP error like a 403 response.
        def mock_requests_get(url, *args, **kwargs):
            raise HTTPError("Forbidden")

        monkeypatch.setattr("requests.get", mock_requests_get)

        response = client.post("/api/students/process-attendance-log")
        assert response.status_code == 200
        resp_json = response.json()
        assert resp_json["sheets_processed"] == 0
        assert resp_json["sheets_failed"] == 1
        mock_postgresql_db.rollback.assert_called_once()

    def test_csv_header_only(self, monkeypatch, mock_postgresql_db):
        """
        Test that a CSV containing only headers (no data rows) is successfully processed.

        - sheets_processed = 1
        - sheets_failed = 0
        """
        attendance_row = Attendance(
            session_id=200,
            link_type="PEARDECK",
            link="https://docs.google.com/spreadsheets/d/HEADER_ONLY_DOC/edit?gid=0#gid=0",
            last_processed_date=None
        )

        query_mock = mock_postgresql_db.query.return_value
        filter_mock = query_mock.filter.return_value
        filter_mock_2 = filter_mock.filter.return_value
        filter_mock_2.all.return_value = [attendance_row]

        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.rollback.return_value = None

        # Mock a response that has only headers in the CSV.
        class MockResponse:
            status_code = 200
            def raise_for_status(self):
                pass
            @property
            def content(self):
                # CSV with only a header row.
                return b"Name,Email,Slide\n"

        def mock_requests_get(url, *args, **kwargs):
            return MockResponse()

        monkeypatch.setattr("requests.get", mock_requests_get)

        response = client.post("/api/students/process-attendance-log")
        assert response.status_code == 200
        resp_json = response.json()
        assert resp_json["sheets_processed"] == 1
        assert resp_json["sheets_failed"] == 0
        mock_postgresql_db.commit.assert_called_once()

    def test_convert_google_sheet_link_invalid(self):
        """
        Test that attempting to convert an invalid Google Sheets URL
        raises a ValueError due to an unparseable doc ID.
        """
        from src.students.attendance_log.service import convert_google_sheet_link_to_csv
        invalid_link = "https://docs.google.com/spreadsheets/invalid_link?gid=0"
        # We expect a ValueError with a specific message substring.
        with pytest.raises(ValueError, match="Unable to parse doc ID from:"):
            convert_google_sheet_link_to_csv(invalid_link)

    def test_unknown_email_goes_to_missing_attendance(self, monkeypatch, mock_postgresql_db):
        """
        Test that when the email in the CSV is not found in the database,
        the row is recorded in missing_attendance and the sheet is still considered processed.
        """
        attendance_row = Attendance(
            session_id=555,
            link_type="PEARDECK",
            link="https://docs.google.com/spreadsheets/d/UNKNOWN_ONLY_DOC/edit?gid=0#gid=0",
            last_processed_date=None
        )

        # Only returns our one attendance row above.
        query_mock = mock_postgresql_db.query.return_value
        filter_mock = query_mock.filter.return_value
        filter_mock_2 = filter_mock.filter.return_value
        filter_mock_2.all.return_value = [attendance_row]

        csv_data = b"""
        Name,Email,Slide
        Unknown Only,unknownonly@example.com,SingleRow
        """

        # Mock the DB to return None for the unknown email.
        class MockResponse:
            status_code = 200
            def raise_for_status(self):
                pass
            @property
            def content(self):
                return csv_data

        def mock_requests_get(url, *args, **kwargs):
            return MockResponse()

        monkeypatch.setattr("requests.get", mock_requests_get)
        # Force the DB to find no matching user for unknownonly@example.com
        filter_mock.first.side_effect = lambda: None

        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.rollback.return_value = None

        response = client.post("/api/students/process-attendance-log")
        assert response.status_code == 200
        resp_json = response.json()
        # Even though the email is unknown, the sheet is still "processed."
        assert resp_json["sheets_processed"] == 1
        assert resp_json["sheets_failed"] == 0

        mock_postgresql_db.commit.assert_called_once()
        mock_postgresql_db.rollback.assert_not_called()

        # Verify that we tried to merge exactly one row into missing_attendance.
        merge_calls = mock_postgresql_db.merge.call_args_list
        assert len(merge_calls) == 1
        missing_obj = merge_calls[0].args[0]
        assert missing_obj.email == "unknownonly@example.com"
        assert missing_obj.session_id == 555
        assert missing_obj.name == "Unknown Only"

    def test_mixed_known_and_unknown_email(self, monkeypatch, mock_postgresql_db):
        """
        Test that a CSV row with a known user is not inserted into missing_attendance,
        while a row with an unknown user is inserted.

        End result:
        - sheets_processed = 1
        - sheets_failed = 0
        - Only the unknown user row is merged into missing_attendance.
        """
        attendance_row = Attendance(
            session_id=999,
            link_type="PEARDECK",
            link="https://docs.google.com/spreadsheets/d/DOC_ID_WITH_MIXED/edit?gid=0#gid=0",
            last_processed_date=None
        )

        # Return a single attendance row to process.
        query_mock = mock_postgresql_db.query.return_value
        filter_mock = query_mock.filter.return_value
        filter_mock_2 = filter_mock.filter.return_value
        filter_mock_2.all.return_value = [attendance_row]

        csv_data = b"""
        Name,Email,Slide
        Known User,knownuser@example.com,Some Slide
        Unknown User,unknownuser@example.com,Another Slide
        """

        # Mock the DB to return a known user for the first email,
        # and None for the second unknown email.
        class MockResponse:
            status_code = 200
            def raise_for_status(self):
                pass
            @property
            def content(self):
                return csv_data

        def mock_requests_get(url, *args, **kwargs):
            return MockResponse()

        monkeypatch.setattr("requests.get", mock_requests_get)

        # First call returns a mock student (known email),
        # second call returns None (unknown email).
        responses = [MagicMock(), None]
        def side_effect_for_first(*args, **kwargs):
            return responses.pop(0) if responses else None

        filter_mock.first.side_effect = side_effect_for_first

        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.rollback.return_value = None

        response = client.post("/api/students/process-attendance-log")
        assert response.status_code == 200
        resp_json = response.json()

        # If we have both known and unknown users, the sheet still "succeeds" overall.
        assert resp_json["sheets_processed"] == 1
        assert resp_json["sheets_failed"] == 0
        mock_postgresql_db.commit.assert_called_once()
        mock_postgresql_db.rollback.assert_not_called()

        # Only the unknown user email should be inserted into missing_attendance.
        merge_calls = mock_postgresql_db.merge.call_args_list
        assert len(merge_calls) == 1
        missing_obj = merge_calls[0].args[0]
        assert missing_obj.email == "unknownuser@example.com"
        assert missing_obj.session_id == 999
        assert missing_obj.name == "Unknown User"
