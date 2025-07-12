from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from pymongo.database import Database as MongoDatabase
from pymongo.client_session import ClientSession as MongoSession
from pymongo.collection import Collection
from pymongo.results import InsertManyResult
import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.applications.master_roster.models import ApplicationWithMasterProps
from src.applications.master_roster.service import (
    add_all_students,
    create_applicant_flex_documents,
    get_all_quiz_submissions,
    get_target_year,
    get_valid_applications,
    remove_duplicate_applicants,
    update_applicant_docs_commitment_status,
    update_applicant_docs_master_added,
)
from src.applications.models import ApplicationModel
from src.config import ACCELERATE_FLEX_COLLECTION, APPLICATIONS_COLLECTION

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
        Test validates the updating of Application collection documents to reflect
        a commitment_quiz_submitted change. Only Application document(s) provided in the
        applications_dict parameter should be updated.
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
        Test validates the successful running of duplicate data (conflicting primary key ids)
        from the applications_dict through in-place mutation.
        """
        mock_row = MagicMock()
        duplicate_id = 2
        mock_row.__getitem__.return_value = duplicate_id

        mock_postgresql_db.execute.return_value.fetchall.return_value = [mock_row]

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
            duplicate_id: ApplicationWithMasterProps( # marked as duplicate in mock query response
                email="test2@cti.com",
                lname="lname2",
                fname="fname2",
                app_submitted=datetime.now(timezone.utc),
                canvas_id=duplicate_id,
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

        assert duplicates_count == 1
        assert len(applications_dict) == 2
        assert 2 not in applications_dict

    def test_remove_duplicate_applicants_fail_all_duplicates(self, mock_postgresql_db):
        """
        Test validates the raising of an HTTPException on the input of all conflicting (duplicate)
        data within applications_dict.
        """
        mock_row_1 = MagicMock()
        mock_row_1.__getitem__.return_value = 1

        mock_row_2 = MagicMock()
        mock_row_2.__getitem__.return_value = 2

        mock_postgresql_db.execute.return_value.fetchall.return_value = [mock_row_1, mock_row_2]

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
            2: ApplicationWithMasterProps(
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
            )
        }

        with pytest.raises(HTTPException, match="No new commitments") as exc_info:
            _ = remove_duplicate_applicants(
                applications_dict=applications_dict,
                postgres_session=mock_postgresql_db
            )
        assert exc_info.value.status_code == 409

    def test_remove_duplicate_applicants_no_duplicates(self, mock_postgresql_db):
        """
        Test validates the accepting of applications_dict containing no duplicate ids
        and no mutations on the dictionary occur.
        """
        mock_postgresql_db.execute.return_value.fetchall.return_value = []

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
            2: ApplicationWithMasterProps(
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

        assert duplicates_count == 0
        assert len(applications_dict) == 3
        assert all(id in applications_dict for id in {1, 2, 3})

    @pytest.mark.parametrize("date_and_expected", [
        # january -> summer of current year
        tuple([datetime(2025, 1, 20), 2025]),

        # may -> summer of current year
        tuple([datetime(2025, 5, 20), 2025]),

        # june -> summer of next year
        tuple([datetime(2025, 6, 20), 2026]),

        # july -> summer of next year
        tuple([datetime(2025, 7, 20), 2026]),

        # december -> summer of next year
        tuple([datetime(2025, 12, 20), 2026]),
    ])
    def test_get_target_year(self, date_and_expected):
        """
        """
        applied_datetime = date_and_expected[0]
        expected_target_year = date_and_expected[1]
        assert get_target_year(date_applied=applied_datetime) == expected_target_year

    def test_update_applicant_docs_master_added_successful_updates(
        self,
        mock_postgresql_db,
        mock_mongo_db: MongoDatabase
    ):
        """
        Test validates that applications included in the applications_dict argument successfully
        have their master_added property set in Mongo. Applications not in this argument are not
        altered.
        """
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
                commitment_quiz_completed=True,
                master_added=False,
            ),
            2: ApplicationWithMasterProps(
                email="test2@cti.com",
                lname="lname2",
                fname="fname2",
                app_submitted=datetime.now(timezone.utc),
                canvas_id=2,
                added_unterview_course=False,
                next_steps_sent=True,
                accessed_unterview=True,
                commitment_quiz_completed=True,
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
                commitment_quiz_completed=True,
                master_added=False,
            )
        }

        test_applications_collection = mock_mongo_db.get_collection(APPLICATIONS_COLLECTION)

        insert_result = test_applications_collection.insert_many([
            model.model_dump() for model in applications_dict.values()
        ])
        assert len(insert_result.inserted_ids) == len(applications_dict)

        # insert app not included in applications_dict
        insert_result = test_applications_collection.insert_one({
            "email": "test4@cti.com",
            "lname": "lname4",
            "fname": "fname4",
            "app_submitted": datetime.now(timezone.utc),
            "canvas_id": 4,
            "master_added": False,
            "commitment_quiz_completed": False
        })

        modified_count = update_applicant_docs_master_added(
            applications_dict=applications_dict,
            application_collection=test_applications_collection,
            mongo_session=None,
            postgres_session=mock_postgresql_db
        )

        mock_postgresql_db.rollback.assert_not_called()
        assert modified_count == 3

        application_documents = test_applications_collection.find()
        for app_doc in application_documents:
            app = ApplicationWithMasterProps(**app_doc)
            assert app.master_added or app.canvas_id == 4

    def test_update_applicant_docs_master_added_missing_apps(self, mock_postgresql_db):
        with pytest.raises(HTTPException, match="Must include at least one application") as exc_info:
            _ = update_applicant_docs_master_added(
                applications_dict={},
                application_collection={},
                mongo_session=None,
                postgres_session=mock_postgresql_db
            )
        assert exc_info.value.status_code == 400
        mock_postgresql_db.rollback.assert_called_once()

    @patch("src.applications.master_roster.service.safe_bulk_write")
    def test_update_applicant_docs_master_added_bad_db_response(
        self,
        mock_safe_bulk_write,
        mock_postgresql_db,
        mock_mongo_db: MongoDatabase
    ):
        """
        Test validates that PostgreSQL rollsback progress on a bad response from the database.

        Note: In the context of the request, the bulk_write to Mongo will NOT be committed as
        there is an exception thrown in this case which closes the ClientSession therein ending
        the transaction.
        """

        mock_result = MagicMock()
        mock_result.acknowledged = False
        mock_result.modified_count = 0
        mock_safe_bulk_write.return_value = mock_result

        applications_dict = {
            1: MagicMock(),
            2: MagicMock(),
            3: MagicMock()
        }

        test_applications_collection = mock_mongo_db.get_collection(APPLICATIONS_COLLECTION)

        with pytest.raises(HTTPException, match="Database failed to acknowledge") as exc_info:
            _ = update_applicant_docs_master_added(
                applications_dict=applications_dict,
                application_collection=test_applications_collection,
                mongo_session=None,
                postgres_session=mock_postgresql_db
            )
        assert exc_info.value.status_code == 500
        mock_postgresql_db.rollback.assert_called_once()

    def test_add_all_students_success_filtering_valid_attributes(self, mock_postgresql_db):
        """
        Test validates the filtering of valid attribute-having dict values in applications_dict.
        Invalid values should not prompt the function to fail but should increment an error
        count as returned by the service function.
        """
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
                commitment_quiz_completed=True,
                master_added=True,
            ),
            2: ApplicationWithMasterProps(
                email="test2@cti.com",
                lname="lname2",
                fname="fname2",
                app_submitted=datetime.now(timezone.utc),
                canvas_id=2,
                added_unterview_course=False,
                next_steps_sent=True,
                accessed_unterview=True,
                commitment_quiz_completed=True,
                master_added=True,
            ),
            3: {
                "invalid": True
            }
        }

        invalid_count = add_all_students(
            applications_dict=applications_dict,
            postgres_session=mock_postgresql_db
        )

        mock_postgresql_db.rollback.assert_not_called()
        assert invalid_count == 1

    def test_add_all_students_raises_db_error(self, mock_postgresql_db):
        """
        Test validates the raising of an HTTPException following the catching of an
        SQLAlchemy error from either `postgres_session.add_all(students)` or
        `postgres_session.flush()`.
        """
        mock_postgresql_db.add_all.side_effect = SQLAlchemyError()

        applications_dict = {}

        with pytest.raises(HTTPException, match="PostgreSQL Database error") as exc_info:
            _ = add_all_students(
                applications_dict=applications_dict,
                postgres_session=mock_postgresql_db
            )
        assert exc_info.value.status_code == 500
        mock_postgresql_db.rollback.assert_called_once()

    def test_create_applicant_flex_documents_success_with_skips(
        self,
        mock_mongo_db: MongoDatabase,
        mock_postgresql_db
    ):
        """
        Test validates the addition of AccelerateFlex documents to the Mongo database. Invalid
        arguments are supplied in an application which should raise a handled exception and
        be acknowledged as a failure to contruct model count.
        """
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
                commitment_quiz_completed=True,
                master_added=True,
            ),
            2: ApplicationWithMasterProps(
                email="test2@cti.com",
                lname="lname2",
                fname="fname2",
                app_submitted=datetime.now(timezone.utc),
                canvas_id=2,
                added_unterview_course=False,
                next_steps_sent=True,
                accessed_unterview=True,
                commitment_quiz_completed=True,
                master_added=True,
            ),
            3: {
                "invalid": True
            }
        }

        invalid_count = create_applicant_flex_documents(
            applications_dict=applications_dict,
            mongo_db=mock_mongo_db,
            mongo_session=None,
            postgres_session=mock_postgresql_db
        )

        for id in [1, 2]:
            flex_doc = mock_mongo_db.get_collection(ACCELERATE_FLEX_COLLECTION).find_one({
                "cti_id": id
            })
            assert flex_doc != None

        assert mock_mongo_db.get_collection(ACCELERATE_FLEX_COLLECTION).find_one({
                "cti_id": 3
        }) == None

        assert invalid_count == 1

    def test_create_applicant_flex_documents_raises_db_error(self, mock_postgresql_db):
        """
        Test validates the raising of an HTTPException following the catching of a failure
        of the Mongo database in acknowledging the AccelerateFlex insert(s). Validation
        includes the rollback of the PostgreSQL database session.
        """
        mock_collection = MagicMock(spec=Collection)
        mock_collection.insert_many.return_value = InsertManyResult(
            inserted_ids=[],
            acknowledged=False
        )

        mock_mongo = MagicMock(spec=MongoDatabase)
        mock_mongo.get_collection.return_value = mock_collection

        applications_dict = {}

        with pytest.raises(HTTPException, match="Database failed to acknowledge flex inserts") as exc_info:
            _ = create_applicant_flex_documents(
                applications_dict=applications_dict,
                mongo_db=mock_mongo,
                mongo_session=None,
                postgres_session=mock_postgresql_db
            )
        assert exc_info.value.status_code == 500
        mock_postgresql_db.rollback.assert_called_once()
