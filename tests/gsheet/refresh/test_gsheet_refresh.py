from fastapi.testclient import TestClient
import pytest
import pandas
import gspread
from datetime import datetime
from os import environ

from src.database.postgres.models import Student, StudentEmail, CanvasID, Ethnicity
from src.main import app
from src.config import settings
from src.database.postgres.core import engine as CONN
from src.database.postgres.core import SessionFactory
import src.gsheet.refresh.service as service

client = TestClient(app)

class TestGSheet:
    @pytest.mark.integration
    @pytest.mark.gsheet
    def testRefreshMain(self, monkeypatch, auth_headers):
        """
        Check that the gspread integration is working, not that it works correctly
        Note that verifying that the sheets match requires type-alignment, which is
        outside the scope of this issue. If Read-Write is solved, it should be implemented.
        """
        # Note that TEST_SHEET_KEY should only ever be called and used in testing
        monkeypatch.setenv("ROSTER_SHEET_KEY", environ.get("TEST_SHEET_KEY"))
        response = client.post("/api/gsheet/refresh/main", headers=auth_headers)
        assert response.status_code == 201

        # Check that at least the correct number of rows were written
        gc = service.create_credentials()
        output_spreadsheet = gc.open_by_key(environ.get("TEST_SHEET_KEY"))
        output_worksheet = output_spreadsheet.worksheet("Main Roster")
        output_df = pandas.DataFrame(output_worksheet.get_all_records())
        roster_data = service.fetch_roster(CONN)

        # Note that modifying the test sheet during the test will break the assertion
        assert output_df.shape == roster_data.shape
        return
    
    @pytest.mark.integration
    @pytest.mark.gsheet
    def testPandasDataframeCreation(self):
        """
        Check that pandas dataframe meets certain sheet requirements
        Columns can be updated, only minimum should be tested

        Note: Since pandas.read_sql() depends on using an actual database, this
        has to be an integration test. Since we can't guarantee the contents
        of the database between tests, we'll focus on verifying the dataframe
        """
        with SessionFactory() as cur_session:
            try:
                # Note even without elements, the actual dataframe should be built correctly
                roster_data = service.fetch_roster(cur_session.connection())
                assert isinstance(roster_data, pandas.DataFrame)
                assert not roster_data.duplicated().any()
                assert {'CTI ID', 'Primary Email Address'}.issubset(roster_data.columns)
            finally:
                cur_session.rollback() # Rollbacks uncommitted changes
                cur_session.close() # Close the session
            return
