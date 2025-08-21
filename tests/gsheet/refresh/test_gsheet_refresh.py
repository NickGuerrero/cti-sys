from fastapi.testclient import TestClient
import pytest
import pandas
import gspread
from datetime import datetime

from src.database.postgres.models import Student, StudentEmail, CanvasID, Ethnicity
from src.main import app
from src.config import settings
from src.database.postgres.core import engine as CONN
from src.database.postgres.core import SessionFactory
import src.gsheet.refresh.service as service

client = TestClient(app)

class TestGSheet:
    @pytest.mark.integration
    def testRefreshMain(self):
        response = client.post("/api/refresh/main", json={
            "fname": "First",
            "lname": "Last",
            "email": "test.user@cti",
            "cohort": True,
            "graduating_year": 2024
        })
        # Verify rows are the same
        # NOTE: This does not check for an absolute match, because data types are likely different
        # Will need more development when determining how to synchronize GSheets and the database
        return
    
    def testPandasMain(self):
        """
        Check that pandas dataframe meets certain sheet requirements
        Columns can be updated, only minimum should be tested
        """
        with SessionFactory() as cur_session:
            # Session creation
            student_a = Student(cti_id=1,fname="Jane",lname="Doe",target_year=2025,
                gender="Female",first_gen=True,institution="SJSU",is_graduate=False,
                birthday=datetime(2000, 11, 29),cohort_lc=False,
                email_addresses=[
                    StudentEmail(email="janedoe@email.com", is_primary=False),
                    StudentEmail(email="janedoe@gmail.com", is_primary=True)],
                canvas_id=CanvasID(canvas_id=100),
                ethnicities=[Ethnicity(ethnicity="Hispanic or Latino"), Ethnicity(ethnicity="Asian")]
            )
            student_b = Student(cti_id=1,fname="John",lname="Doe",target_year=2025,
                gender="Male",first_gen=True,institution="SJSU",is_graduate=False,
                birthday=datetime(2000, 11, 29),cohort_lc=False,
                email_addresses=[StudentEmail(email="johndoe@gmail.com", is_primary=True)],
                canvas_id=CanvasID(canvas_id=100),
                ethnicities=[Ethnicity(ethnicity="Hispanic or Latino")]
            )
            cur_session.add_all([student_a, student_b])
            # Actual Test
            roster_data = service.fetch_roster(cur_session.connection())
            assert isinstance(roster_data, pandas.DataFrame)
            assert not roster_data.duplicated().any()
            assert {'id', 'email'}.issubset(roster_data.columns)
            return
