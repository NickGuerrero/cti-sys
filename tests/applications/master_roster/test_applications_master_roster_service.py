from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from pymongo.database import Database as MongoDatabase
from pymongo.client_session import ClientSession as MongoSession
import pytest

from src.applications.master_roster.models import ApplicationWithMasterProps
from src.applications.master_roster.service import add_all_students, create_applicant_flex_documents, get_all_quiz_submissions, get_target_year, get_valid_applications, remove_duplicate_applicants, update_applicant_docs_commitment_status, update_applicant_docs_master_added
from src.applications.models import ApplicationModel
from src.config import APPLICATIONS_COLLECTION

class TestMasterRosterServices:
    @pytest.mark.canvas
    @pytest.mark.integration
    def test_get_all_quiz_submissions_integration(self):
        """
        Test validates connection with Canvas API. Marked with Canvas and Integration
        to avoid running in unauthenticated or non-production test environments.

        Assumes the proper setting of production IDs for both the course and the quiz
        (Commitment Quiz).
        """
        submissions_user_ids = get_all_quiz_submissions()
        assert isinstance(submissions_user_ids, set)
        assert all(isinstance(uid, int) for uid in submissions_user_ids)

    def test_get_all_quiz_submissions_pagination(self):
        """
        Test validates the functionality of pagination using mocked external API responses.
        """
        ex_quiz_submission = {
            "id": "123",
            "quiz_id": "456",
            "user_id": "789",
            "submission_id": "1011",
            "started_at": "2025-07-11T10:00:00Z",
            "finished_at": "2025-07-11T10:30:00Z",
            "end_at": "2025-07-11T11:00:00Z",
            "attempt": "1",
            "extra_attempts": "0",
            "extra_time": "5",
            "manually_unlocked": "true",
            "time_spent": "1800",
            "score": "95.5",
            "score_before_regrade": "90.0",
            "kept_score": "95.5",
            "fudge_points": "0.5",
            "has_seen_results": "true",
            "workflow_state": "complete",
            "overdue_and_needs_submission": "false"
        }
        
        user_1_submission = deepcopy(ex_quiz_submission)
        user_1_submission["user_id"] = 1
        user_2_submission = deepcopy(ex_quiz_submission)
        user_2_submission["user_id"] = 2
        first_page = MagicMock()
        first_page.json.return_value = {
            "quiz_submissions": [user_1_submission, user_2_submission]
        }
        first_page.links = {"next": {"url": "http://next-page.com"}}
        first_page.raise_for_status = lambda: None

        user_3_submission = deepcopy(ex_quiz_submission)
        user_3_submission["user_id"] = 3
        user_4_submission = deepcopy(ex_quiz_submission)
        user_4_submission["user_id"] = 4
        second_page = MagicMock()
        second_page.json.return_value = {
            "quiz_submissions": [user_3_submission, user_4_submission]
        }
        second_page.links = {"next": {"url": "http://last-page.com"}}
        second_page.raise_for_status = lambda: None

        user_5_submission = deepcopy(ex_quiz_submission)
        user_5_submission["user_id"] = 5
        third_page = MagicMock()
        third_page.json.return_value = {
            "quiz_submissions": [user_5_submission]
        }
        third_page.links = {}
        third_page.raise_for_status = lambda: None

        with patch("src.applications.master_roster.service.get", side_effect=[first_page, second_page, third_page]):
            submissions_user_ids = get_all_quiz_submissions()

        assert submissions_user_ids == {1, 2, 3, 4, 5}

    def test_get_all_quiz_submissions_raises_validation_error(self):
        """
        Test validates that invalid QuizSubmission data from the Canvas API would
        throw a ValidationError which is then caught and thrown to the route response as
        an HTTPException 422.
        """
        user_1_submission = {
            "id": "123",
            # "quiz_id": "456", required field missing on QuizSubmission
            "user_id": "1",
            "submission_id": "1011",
            "started_at": "2025-07-11T10:00:00Z",
            "finished_at": "2025-07-11T10:30:00Z",
            "end_at": "2025-07-11T11:00:00Z",
            "attempt": "1",
            "extra_attempts": "0",
            "extra_time": "5",
            "manually_unlocked": "true",
            "time_spent": "1800",
            "score": "95.5",
            "score_before_regrade": "90.0",
            "kept_score": "95.5",
            "fudge_points": "0.5",
            "has_seen_results": "true",
            "workflow_state": "complete",
            "overdue_and_needs_submission": "false"
        }
        first_page = MagicMock()
        first_page.json.return_value = {
            "quiz_submissions": [user_1_submission]
        }
        first_page.links = {}
        first_page.raise_for_status = lambda: None

        with patch("src.applications.master_roster.service.get", side_effect=[first_page]):
            with pytest.raises(HTTPException, match="Invalid quiz submission data found:") as exc_info:
                _ = get_all_quiz_submissions()
            assert exc_info.value.status_code == 422

    def test_get_valid_applications_success(self, mock_mongo_db: MongoDatabase):
        """
        Test validates the retrieval of properly filtered Application documents. Does not
        validate the data imported to the Application collection as JSON Schema validation
        is bypassed by using MongoMock.
        """
        test_applications_collection = mock_mongo_db.get_collection(APPLICATIONS_COLLECTION)
        applications = [
            ApplicationWithMasterProps(
                email="test1@cti.com",
                lname="lname1",
                fname="fname1",
                app_submitted=datetime.now(timezone.utc),
                canvas_id=1,
                added_unterview_course=False,
                next_steps_sent=True,
                accessed_unterview=True,
                commitment_quiz_completed=False,
                master_added=False,
            ),
            ApplicationModel( # defaults set for filtered-for props should prompt inclusion
                email="test2@cti.com",
                lname="lname2",
                fname="fname2",
                app_submitted=datetime.now(timezone.utc),
                canvas_id=2,
            ),
            ApplicationWithMasterProps( # added to master, should NOT include
                email="test3@cti.com",
                lname="lname3",
                fname="fname3",
                app_submitted=datetime.now(timezone.utc),
                canvas_id=3,
                added_unterview_course=False,
                next_steps_sent=True,
                accessed_unterview=True,
                commitment_quiz_completed=True,
                master_added=True,
            )
        ]

        insert_result = test_applications_collection.insert_many([
            model.model_dump() for model in applications
        ])
        assert len(insert_result.inserted_ids) == len(applications)

        # insert app missing required ApplicationWithMasterProps attributes, should be only invalid
        insert_result = test_applications_collection.insert_one({
            "email": "test4@cti.com",
            "lname": "lname4",
            # "fname": "fname4", missing required fname attribute
            "app_submitted": datetime.now(timezone.utc),
            "canvas_id": 4,
            "master_added": False,
            "commitment_quiz_completed": False
        })

        valid_submissions_user_ids = {1, 2}
        invalid_or_rejected_user_ids = {3, 4}

        applications_dict, invalid_applications_count = get_valid_applications(
            application_collection=test_applications_collection,
            mongo_session=MagicMock(spec=MongoSession),
            submission_user_ids=valid_submissions_user_ids.union(invalid_or_rejected_user_ids)
        )

        assert len(applications_dict) == 2
        assert invalid_applications_count == 1
        assert all(id in applications_dict for id in valid_submissions_user_ids)
        assert all(id not in applications_dict for id in invalid_or_rejected_user_ids)

    def test_get_valid_applications_success_found_none(self, mock_mongo_db: MongoDatabase):
        """
        Test validates that no users may be found to match the submissions user_id values provided
        without raising exceptions.
        """
        test_applications_collection = mock_mongo_db.get_collection(APPLICATIONS_COLLECTION)
        submissions_user_ids = {1, 2, 3, 4}

        applications_dict, invalid_applications_count = get_valid_applications(
            application_collection=test_applications_collection,
            mongo_session=MagicMock(spec=MongoSession),
            submission_user_ids=submissions_user_ids
        )

        assert len(applications_dict) == 0
        assert invalid_applications_count == 0

    def test_update_applicant_docs_commitment_status_successful_updates(self, mock_mongo_db: MongoDatabase):
        """
        """
        pass
        test_applications_collection = mock_mongo_db.get_collection(APPLICATIONS_COLLECTION)
        applications = [
            ApplicationWithMasterProps(
                email="test1@cti.com",
                lname="lname1",
                fname="fname1",
                app_submitted=datetime.now(timezone.utc),
                canvas_id=1,
                added_unterview_course=False,
                next_steps_sent=True,
                accessed_unterview=True,
                commitment_quiz_completed=False,
                master_added=False,
            ),
            ApplicationWithMasterProps(
                email="test2@cti.com",
                lname="lname2",
                fname="fname2",
                app_submitted=datetime.now(timezone.utc),
                canvas_id=2,
                added_unterview_course=False,
                next_steps_sent=True,
                accessed_unterview=True,
                commitment_quiz_completed=False,
                master_added=False,
            ),
            ApplicationWithMasterProps(
                email="test3@cti.com",
                lname="lname3",
                fname="fname3",
                app_submitted=datetime.now(timezone.utc),
                canvas_id=3,
                added_unterview_course=False,
                next_steps_sent=True,
                accessed_unterview=True,
                commitment_quiz_completed=False,
                master_added=False,
            )
        ]

        insert_result = test_applications_collection.insert_many([
            model.model_dump() for model in applications
        ])
        assert len(insert_result.inserted_ids) == len(applications)
        update_applicant_docs_commitment_status(
            application_collection=test_applications_collection,
            mongo_session=None,
            applications_dict={
                1: applications[0],
                # 2: applications[1], skipped & should not be altered
                3: applications[2]
            }
        )

        application_documents = test_applications_collection.find()
        for app_doc in application_documents:
            app = ApplicationWithMasterProps(**app_doc)
            assert app.commitment_quiz_completed or app.canvas_id == 2

    def test_update_applicant_docs_commitment_status_missing_apps(self, mock_mongo_db: MongoDatabase):
        """
        Test validates that the lack of any applications provided through applications_dict raises
        an HTTPException.
        """
        test_applications_collection = mock_mongo_db.get_collection(APPLICATIONS_COLLECTION)

        with pytest.raises(HTTPException, match="Must contain at least one application") as exc_info:
            update_applicant_docs_commitment_status(
                application_collection=test_applications_collection,
                mongo_session=MagicMock(spec=MongoSession),
                applications_dict={}
            )
        assert exc_info.value.status_code == 400

    def test_remove_duplicate_applicants_pops_duplicates(self, mock_postgresql_db):
        """
        """
        mock_row_1 = MagicMock()
        mock_row_1.__getitem__.return_value = 2
        mock_row_1.cti_id = 2

        mock_postgresql_db.exectute.return_value.fetch_all.return_value = [mock_row_1]

        applications_dict = {
            1: ApplicationWithMasterProps(
                email="test1@cti.com",
                lname="lname1",
                fname="fname1",
                app_submitted=datetime.now(timezone.utc),
                canvas_id=1,
                added_unterview_course=False,
                next_steps_sent=True,
                accessed_unterview=True,
                commitment_quiz_completed=False,
                master_added=False,
            ),
            2: ApplicationWithMasterProps( # marked as duplicate in mock query response
                email="test2@cti.com",
                lname="lname2",
                fname="fname2",
                app_submitted=datetime.now(timezone.utc),
                canvas_id=2,
                added_unterview_course=False,
                next_steps_sent=True,
                accessed_unterview=True,
                commitment_quiz_completed=False,
                master_added=False,
            ),
            3: ApplicationWithMasterProps(
                email="test3@cti.com",
                lname="lname3",
                fname="fname3",
                app_submitted=datetime.now(timezone.utc),
                canvas_id=3,
                added_unterview_course=False,
                next_steps_sent=True,
                accessed_unterview=True,
                commitment_quiz_completed=False,
                master_added=False,
            ),
        }

        duplicates_count = remove_duplicate_applicants(
            applications_dict=applications_dict,
            postgres_session=mock_postgresql_db
        )

        assert len(applications_dict) == 2
        assert 2 not in applications_dict
        assert duplicates_count == 1

    def test_remove_duplicate_applicants_fail_all_duplicates(self, mock_postgresql_db):
        """
        """
        remove_duplicate_applicants(applications_dict={}, postgres_session=mock_postgresql_db)

    def test_remove_duplicate_applicants_no_duplicates(self, mock_postgresql_db):
        """
        """
        remove_duplicate_applicants(applications_dict={}, postgres_session=mock_postgresql_db)

    def test_get_target_year(self):
        """
        """
        get_target_year(...)

    def test_update_applicant_docs_master_added_successful_updates(self):
        """
        """
        update_applicant_docs_master_added(...)

    def test_add_all_students(self):
        """
        """
        add_all_students(...)

    def create_applicant_flex_documents(self):
        """
        """
        create_applicant_flex_documents(...)
