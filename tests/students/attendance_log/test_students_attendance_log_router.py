import pytest
from unittest.mock import MagicMock
from src.database.postgres.models import Attendance

class TestProcessAttendanceLog:
    
    def setup_attendance_query(self, mock_db, attendance_rows):
        """Helper to mock the initial attendance query"""
        query_mock = mock_db.query.return_value
        filter_mock = query_mock.filter.return_value
        filter_mock_2 = filter_mock.filter.return_value
        filter_mock_2.all.return_value = attendance_rows
        mock_db.commit.return_value = None
        mock_db.rollback.return_value = None
    
    def setup_gspread_worksheet(self, mock_client, worksheet_data, doc_id="FAKE_DOC_ID"):
        """Helper to mock gspread worksheet"""
        mock_worksheet = MagicMock()
        mock_worksheet.get_all_values.return_value = worksheet_data
        mock_worksheet.id = 0
        
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.worksheets.return_value = [mock_worksheet]
        
        mock_client.open_by_url.return_value = mock_spreadsheet
        return mock_worksheet, mock_spreadsheet

    def setup_db_queries_for_unknown_email(self, mock_db, attendance_row):
        """Helper for unknown email query setup"""
        query_count = [0]
        
        def query_side_effect(model):
            query_count[0] += 1
            mock_query = MagicMock()
            mock_filter = MagicMock()
            mock_filter2 = MagicMock()
            
            if query_count[0] == 1:
                mock_filter2.all.return_value = [attendance_row]
            else:
                mock_filter.first.return_value = None
                mock_filter2.first.return_value = None
            
            mock_filter.filter.return_value = mock_filter2
            mock_query.filter.return_value = mock_filter
            return mock_query
        
        mock_db.query.side_effect = query_side_effect
        mock_db.commit.return_value = None
        mock_db.rollback.return_value = None

    def setup_db_queries_for_mixed_emails(self, mock_db, attendance_row):
        """Helper for mixed known/unknown email query setup"""
        query_count = [0]
        
        def query_side_effect(model):
            query_count[0] += 1
            mock_query = MagicMock()
            mock_filter = MagicMock()
            mock_filter2 = MagicMock()
            
            if query_count[0] == 1:
                # Initial attendance query
                mock_filter2.all.return_value = [attendance_row]
            elif query_count[0] == 2:
                # First email (known)
                mock_filter.first.return_value = MagicMock(cti_id=1)
                mock_filter2.first.return_value = MagicMock(cti_id=1)
            else:
                # All other queries return None
                mock_filter.first.return_value = None
                mock_filter2.first.return_value = None
            
            mock_filter.filter.return_value = mock_filter2
            mock_query.filter.return_value = mock_filter
            return mock_query
        
        mock_db.query.side_effect = query_side_effect
        mock_db.commit.return_value = None
        mock_db.rollback.return_value = None
        mock_db.add.return_value = None

    @pytest.mark.parametrize(
        "worksheet_data, expected_processed, expected_failed",
        [
            # Valid worksheet
            (
                [
                    ["Name", "Email", "Slide 1", "Slide 2"],
                    ["Jane Doe", "jane@example.com", "Hello", "World"],
                    ["John Doe", "john@example.com", "Yes", "No"]
                ],
                1, 0,
            ),
            # Missing 'Name' column
            (
                [
                    ["Email", "Slide 1", "Slide 2"],
                    ["someone@example.com", "Answer1", "Answer2"]
                ],
                0, 1
            )
        ]
    )
    def test_process_attendance_log_simple(
        self,
        client,
        worksheet_data,
        expected_processed,
        expected_failed,
        mock_gspread,
        mock_postgresql_db,
    ):
        """Test processing with valid and invalid worksheets"""
        attendance_row = Attendance(
            session_id=2,
            link_type="PEARDECK",
            link="https://docs.google.com/spreadsheets/d/FAKE_DOC_ID/edit",
            last_processed_date=None
        )

        self.setup_attendance_query(mock_postgresql_db, [attendance_row])
        self.setup_gspread_worksheet(mock_gspread, worksheet_data)

        response = client.post("/api/students/process-attendance-log")
        
        assert response.status_code == 200
        resp_json = response.json()
        assert resp_json["sheets_processed"] == expected_processed
        assert resp_json["sheets_failed"] == expected_failed

        if expected_processed:
            mock_postgresql_db.commit.assert_called_once()
        if expected_failed:
            mock_postgresql_db.rollback.assert_called_once()

    def test_multiple_attendance_rows_partial_fail(self, client, mock_gspread, mock_postgresql_db):
        """Test multiple sheets with some failing"""
        rows = [
            Attendance(session_id=10+i, link_type="PEARDECK", link=f"https://docs.google.com/spreadsheets/d/DOC_ID_{name}/edit", last_processed_date=None)
            for i, name in enumerate(["s1", "s2", "s3", "fail"])
        ]

        # Need to setup the query to return all rows initially
        query_mock = mock_postgresql_db.query.return_value
        filter_mock = query_mock.filter.return_value
        filter_mock_2 = filter_mock.filter.return_value
        filter_mock_2.all.return_value = rows
        
        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.rollback.return_value = None

        # Map doc IDs to worksheet data
        data_map = {
            "DOC_ID_s1": [["Name", "Email", "Slide"], ["Person", "p@ex.com", "Yes"]],
            "DOC_ID_s2": [["Name", "Email", "Slide"], ["Person", "p@ex.com", "Yes"]],
            "DOC_ID_s3": [["Name", "Email", "Slide"], ["Person", "p@ex.com", "Yes"]],
            "DOC_ID_fail": [["Email", "Slide"], ["p@ex.com", "NoName"]],
        }

        def mock_open_by_url(url):
            doc_id = url.split("/d/")[1].split("/")[0]
            worksheet_data = data_map.get(doc_id, [[]])
            mock_worksheet = MagicMock()
            mock_worksheet.get_all_values.return_value = worksheet_data
            mock_worksheet.id = 0
            mock_spreadsheet = MagicMock()
            mock_spreadsheet.worksheets.return_value = [mock_worksheet]
            mock_spreadsheet.get_worksheet.return_value = mock_worksheet
            return mock_spreadsheet
        
        mock_gspread.open_by_url.side_effect = mock_open_by_url

        response = client.post("/api/students/process-attendance-log")
        resp_json = response.json()

        assert resp_json["sheets_processed"] == 3
        assert resp_json["sheets_failed"] == 1
        assert mock_postgresql_db.commit.call_count == 3
        assert mock_postgresql_db.rollback.call_count == 1

    def test_empty_worksheet_fails(self, client, mock_gspread, mock_postgresql_db):
        """Test empty worksheet failure"""
        attendance_row = Attendance(
            session_id=5, link_type="PEARDECK",
            link="https://docs.google.com/spreadsheets/d/EMPTY/edit",
            last_processed_date=None
        )

        self.setup_attendance_query(mock_postgresql_db, [attendance_row])
        # Empty worksheet
        self.setup_gspread_worksheet(mock_gspread, [])  

        response = client.post("/api/students/process-attendance-log")
        resp_json = response.json()
        
        assert resp_json["sheets_processed"] == 0
        assert resp_json["sheets_failed"] == 1
        mock_postgresql_db.rollback.assert_called_once()

    def test_gspread_error(self, client, mock_gspread, mock_postgresql_db):
        """Test gspread API error handling"""
        attendance_row = Attendance(
            session_id=99, link_type="PEARDECK",
            link="https://docs.google.com/spreadsheets/d/PROTECTED/edit",
            last_processed_date=None
        )

        self.setup_attendance_query(mock_postgresql_db, [attendance_row])
        mock_gspread.open_by_url.side_effect = Exception("Permission denied")

        response = client.post("/api/students/process-attendance-log")
        resp_json = response.json()
        
        assert resp_json["sheets_processed"] == 0
        assert resp_json["sheets_failed"] == 1
        mock_postgresql_db.rollback.assert_called_once()

    def test_worksheet_header_only(self, client, mock_gspread, mock_postgresql_db):
        """Test worksheet with only headers (no data rows)"""
        attendance_row = Attendance(
            session_id=200, link_type="PEARDECK",
            link="https://docs.google.com/spreadsheets/d/HEADER_ONLY/edit",
            last_processed_date=None
        )

        self.setup_attendance_query(mock_postgresql_db, [attendance_row])
        self.setup_gspread_worksheet(mock_gspread, [["Name", "Email", "Slide 1"]])

        response = client.post("/api/students/process-attendance-log")
        resp_json = response.json()
        
        assert resp_json["sheets_processed"] == 1
        assert resp_json["sheets_failed"] == 0
        assert attendance_row.student_count == 0

    def test_unknown_email_goes_to_missing_attendance(self, client, mock_gspread, mock_postgresql_db):
        """Test unknown email creates missing_attendance record"""
        attendance_row = Attendance(
            session_id=555, link_type="PEARDECK",
            link="https://docs.google.com/spreadsheets/d/UNKNOWN/edit",
            last_processed_date=None
        )

        worksheet_data = [
            ["Name", "Email", "Slide 1"],
            ["Unknown", "unknown@ex.com", "Answer"]
        ]

        self.setup_gspread_worksheet(mock_gspread, worksheet_data)
        self.setup_db_queries_for_unknown_email(mock_postgresql_db, attendance_row)

        response = client.post("/api/students/process-attendance-log")
        resp_json = response.json()
        
        assert resp_json["sheets_processed"] == 1
        assert resp_json["sheets_failed"] == 0

        merge_calls = mock_postgresql_db.merge.call_args_list
        assert len(merge_calls) == 1
        assert merge_calls[0].args[0].email == "unknown@ex.com"

    def test_mixed_known_and_unknown_email(self, client, mock_gspread, mock_postgresql_db):
        """Test mix of known and unknown emails"""
        attendance_row = Attendance(
            session_id=999, link_type="PEARDECK",
            link="https://docs.google.com/spreadsheets/d/MIXED/edit",
            last_processed_date=None
        )

        worksheet_data = [
            ["Name", "Email", "Slide 1"],
            ["Known", "known@ex.com", "Answer"],
            ["Unknown", "unknown@ex.com", "Answer"]
        ]

        self.setup_gspread_worksheet(mock_gspread, worksheet_data)
        self.setup_db_queries_for_mixed_emails(mock_postgresql_db, attendance_row)

        response = client.post("/api/students/process-attendance-log")
        resp_json = response.json()
        
        assert resp_json["sheets_processed"] == 1
        assert resp_json["sheets_failed"] == 0

        # Only unknown email should be merged
        merge_calls = mock_postgresql_db.merge.call_args_list
        assert len(merge_calls) == 1
        assert merge_calls[0].args[0].email == "unknown@ex.com"

    @pytest.mark.parametrize("first_slide, last_slide, expected_full_attendance", [
        ("Yes", "Yes", True), # Both filled
        ("Yes", "", False), # Last empty
        ("", "Yes", False), # First empty
        ("", "", False), # Both empty
    ])
    def test_full_attendance_logic(self, client, mock_gspread, mock_postgresql_db, first_slide, last_slide, expected_full_attendance):
        """Test full_attendance flag with different slide combinations"""
        attendance_row = Attendance(
            session_id=300, link_type="PEARDECK",
            link="https://docs.google.com/spreadsheets/d/ATT_TEST/edit",
            last_processed_date=None
        )

        worksheet_data = [
            ["Name", "Email", "Slide 1", "Slide 2", "Slide 3"],
            ["Student", "student@ex.com", first_slide, "Maybe", last_slide]
        ]

        self.setup_attendance_query(mock_postgresql_db, [attendance_row])
        self.setup_gspread_worksheet(mock_gspread, worksheet_data)

        # Mock student email found
        query_mock = mock_postgresql_db.query.return_value
        filter_mock = query_mock.filter.return_value
        filter_mock.first.side_effect = [MagicMock(cti_id=1), None]

        mock_attendance_obj = []
        mock_postgresql_db.add.side_effect = lambda obj: mock_attendance_obj.append(obj)

        response = client.post("/api/students/process-attendance-log")
        
        assert response.status_code == 200
        assert len(mock_attendance_obj) == 1
        assert mock_attendance_obj[0].full_attendance is expected_full_attendance

    def test_student_count_multiple_students(self, client, mock_gspread, mock_postgresql_db):
        """Test student_count reflects number of data rows"""
        attendance_row = Attendance(
            session_id=101, link_type="PEARDECK",
            link="https://docs.google.com/spreadsheets/d/COUNT_TEST/edit",
            last_processed_date=None
        )

        worksheet_data = [
            ["Name", "Email", "Slide 1"],
            ["Alice", "alice@ex.com", "Yes"],
            ["Bob", "bob@ex.com", "Yes"],
            ["Charlie", "charlie@ex.com", "No"]
        ]

        self.setup_attendance_query(mock_postgresql_db, [attendance_row])
        self.setup_gspread_worksheet(mock_gspread, worksheet_data)

        response = client.post("/api/students/process-attendance-log")
        
        assert response.status_code == 200
        assert attendance_row.student_count == 3