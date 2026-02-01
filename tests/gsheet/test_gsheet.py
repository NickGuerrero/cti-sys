import pytest
from os import environ
import pandas
from datetime import date

import src.gsheet.utils as utils
import src.gsheet.group_attendance.service as service
from src.database.postgres.core import engine as CONN


class TestGSheetGroup:
    @pytest.mark.integration
    @pytest.mark.gsheet
    def testGroupAttendance(self, monkeypatch, client):
        monkeypatch.setenv("ROSTER_SHEET_KEY", environ.get("TEST_SHEET_KEY"))
        response = client.post("/api/gsheet/group-attendance",
                               params={
                                   "spreadsheet_id": environ.get("TEST_SHEET_KEY"),
                                   "spreadsheet_name": "Test Group", # You can change this later to proper spreadsheet name
                                   "start_date": date(2025, 10, 1),
                                   "end_date": date(2025, 10, 15)
                               },
                            )
        assert response.status_code == 201

        gc = utils.create_credentials()
        output_spreadsheet = gc.open_by_key(environ.get("TEST_SHEET_KEY"))
        # Create a sheet in the spreadsheet called Test Group to test the endpoint.
        output_worksheet = output_spreadsheet.worksheet("Test Group")
        output_df = pandas.DataFrame(output_worksheet.get_all_records())

        cti_ids = service.fetch_cti_ids_from_sheet(environ.get("TEST_SHEET_KEY"), "Test Group", gc)
        attendance_data = service.fetch_group_attendance(CONN, date(2025, 10, 1), date(2025, 10, 15), cti_ids)

        print(attendance_data)
        print(output_df)

        # Note that modifying the test sheet during the test will break the assertion
        assert output_df.shape == attendance_data.shape
        return