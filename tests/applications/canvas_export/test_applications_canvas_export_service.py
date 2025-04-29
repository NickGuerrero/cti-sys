from datetime import datetime, timezone
from fastapi import HTTPException
from pymongo.database import Database
import pytest

from src.applications.canvas_export.service import get_unenrolled_application_documents
from src.applications.models import ApplicationModel
from src.config import APPLICATIONS_COLLECTION

class TestCanvasExportServices:
    def test_get_unenrolled_application_documents_none_found(self, mock_mongo_db: Database):
        """
        Test validates function error response if no applicants are unenrolled.
        """
        with pytest.raises(HTTPException, match="No unenrolled applicants found"):
            get_unenrolled_application_documents(db=mock_mongo_db)

    def test_get_unenrolled_application_documents_finds_filtered_applicants(self, mock_mongo_db: Database):
        """
        Test validates function fetching documents for only unenrolled or not yet added to Canvas Applicants.
        """
        applications = [
            # applicants not yet added to Canvas nor enrolled in Unterview -> should be processed
            ApplicationModel(
                email="test1@cti.com",
                lname="last1",
                fname="first1",
                app_submitted=datetime.now(timezone.utc)
            ),
            ApplicationModel(
                email="test2@cti.com",
                lname="last2",
                fname="first2",
                app_submitted=datetime.now(timezone.utc),
                last_batch_update=datetime.now(timezone.utc)
            ),
            # applicants added to Canvas but not yet enrolled in Unterview -> should be processed
            ApplicationModel(
                email="test3@cti.com",
                lname="last3",
                fname="first3",
                app_submitted=datetime.now(timezone.utc),
                canvas_id=3,
                last_batch_update=datetime.now(timezone.utc)
            ),
            ApplicationModel(
                email="test4@cti.com",
                lname="last4",
                fname="first4",
                app_submitted=datetime.now(timezone.utc),
                canvas_id=4,
                last_batch_update=datetime.now(timezone.utc)
            ),
            # applicants both added to Canvas and enrolled in Unterview -> not processed
            ApplicationModel(
                email="test5@cti.com",
                lname="last5",
                fname="first5",
                app_submitted=datetime.now(timezone.utc),
                canvas_id=5,
                added_unterview_course=True,
                last_batch_update=datetime.now(timezone.utc)
            ),
            ApplicationModel(
                email="test6@cti.com",
                lname="last6",
                fname="first6",
                app_submitted=datetime.now(timezone.utc),
                canvas_id=6,
                added_unterview_course=True,
                last_batch_update=datetime.now(timezone.utc)
            ),
        ]

        mock_mongo_db.get_collection(APPLICATIONS_COLLECTION).insert_many([
            model.model_dump() for model in applications
        ])
        unenrolled_application_documents = get_unenrolled_application_documents(db=mock_mongo_db)

        assert len(unenrolled_application_documents) == 4
