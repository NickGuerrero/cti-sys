from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from pymongo.database import Database as MongoDatabase
import pytest

from src.applications.canvas_export.schemas import CanvasExportResponse
from src.applications.models import ApplicationModel
from src.config import APPLICATIONS_COLLECTION
from src.main import app

client = TestClient(app)

class TestCanvasExport:
    @pytest.mark.integration
    def test_add_applicants_to_canvas(self, real_mongo_db: MongoDatabase):
        """
        Integration test validating a successful external API interaction and handling.

        Test utilizes overridden Canvas API URL linked to the test environment.
        """
        test_applications_collection = real_mongo_db.get_collection(APPLICATIONS_COLLECTION)

        # 2. Add applications to test MongoDB
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
                last_batch_update=None
            ),
            # applicants added to Canvas but not yet enrolled in Unterview -> should be processed
            ApplicationModel(
                email="test3@cti.com",
                lname="last3",
                fname="first3",
                app_submitted=datetime.now(timezone.utc),
                last_batch_update=None
            ),
            ApplicationModel(
                email="test4@cti.com",
                lname="last4",
                fname="first4",
                app_submitted=datetime.now(timezone.utc),
                last_batch_update=None
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

        insert_result = test_applications_collection.insert_many([
            model.model_dump() for model in applications
        ])
        assert insert_result.acknowledged and len(insert_result.inserted_ids) == len(applications)

        # 3. Initiate endpoint request and validate success
        response = client.post("/api/applications/canvas-export")
        assert response.status_code == 200
        import_data = CanvasExportResponse(**response.json())

        assert import_data.batch_date < datetime.now(timezone.utc)
        assert import_data.applicants_enrolled == 4

        # 4. Validate applicants processed in batch have been updated on MongoDB
        newly_enrolled_application_documents = test_applications_collection.find({
            "_id": {
                "$in": insert_result.inserted_ids
            }
        })
        newly_enrolled_applications = [ApplicationModel(**doc) for doc in list(newly_enrolled_application_documents)]
        for newly_enrolled_application in newly_enrolled_applications:
            unenrolled_application = next(
                (unenrolled for unenrolled in applications if unenrolled.email == newly_enrolled_application.email),
            None)

            # verify state of attributes not related to the export are unchanged
            assert unenrolled_application.fname == newly_enrolled_application.fname
            assert unenrolled_application.lname == newly_enrolled_application.lname

            # verify batch attributes have been updated
            assert newly_enrolled_application.added_unterview_course
            time_delta = abs(newly_enrolled_application.last_batch_update.replace(tzinfo=timezone.utc) - import_data.batch_date)
            assert time_delta < timedelta(milliseconds=100)
            assert newly_enrolled_application.canvas_id is not None
