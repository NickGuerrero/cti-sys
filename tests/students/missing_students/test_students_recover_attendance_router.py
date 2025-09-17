import pytest
from types import SimpleNamespace
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from src.main import app
from src.config import settings
from src.students.missing_students import service

client = TestClient(app)


class TestRecoverAttendance:
    def test_no_missing_records(self, monkeypatch, mock_postgresql_db):
        """
        Test the case where there are no MissingAttendance records.
        """
        class EmptyResult:
            def all(self):
                return []

        # Stub execute().all() to return an empty list
        mock_postgresql_db.execute.return_value = EmptyResult()

        # Stub process_matches to return an empty list
        monkeypatch.setattr(service, "process_matches", lambda db_session, matches: [])

        response = client.post("/api/students/recover-attendance")
        assert response.status_code == 200
        assert response.json() == {"status": 200, "moved": 0}

        mock_postgresql_db.commit.assert_not_called()


    @pytest.mark.parametrize("env", ["production", "development"])
    def test_move_single_record(self, env, monkeypatch, mock_postgresql_db):
        """
        Test the case where there is one match for MissingAttendance.
        The endpoint should return moved=1, and in development env rows 
        should contain the moved row with details like email, name, cti_id.
        """
        monkeypatch.setattr(settings, "app_env", env)

        # Create a fake MissingAttendance row and its cti_id match
        missing_row = SimpleNamespace(
            email="foo@example.com",
            name="Foo User",
            session_id=10,
            peardeck_score=0.8,
        )
        matches = [(missing_row, 123)]

        class OneResult:
            def all(self):
                return matches

        # Stub execute().all() to return our single match
        mock_postgresql_db.execute.return_value = OneResult()

        # Stub process_matches to return a moved row
        moved_row = {"email": "foo@example.com", "name": "Foo User", "cti_id": 123}

        # Define a fake process_matches function that returns our moved_row
        def fake_process(db_session, got_matches):
            assert got_matches == matches
            return [moved_row]

        monkeypatch.setattr(service, "process_matches", fake_process)
        mock_postgresql_db.commit.return_value = None
        response = client.post("/api/students/recover-attendance")
        assert response.status_code == 200

        data = response.json()
        if env == "production":
            assert data == {"status": 200, "moved": 1}
        else:
            assert data["status"] == 200
            assert data["moved"] == 1
            # In development, rows should contain the moved row with email, name, cti_id
            assert data["rows"] == [moved_row]

        mock_postgresql_db.commit.assert_called_once()


    @pytest.mark.parametrize("env", ["production", "development"])
    def test_move_multiple_records(self, env, monkeypatch, mock_postgresql_db):
        """
        Test the case where there are multiple matches for MissingAttendance.
        The endpoint should return moved=2, and in development env rows 
        should contain both moved rows with their details.
        """
        monkeypatch.setattr(settings, "app_env", env)

        # Create two fake MissingAttendance rows and their cti_id matches
        missing_row1 = SimpleNamespace(
            email="alice@example.com",
            name="Alice User",
            session_id=20,
            peardeck_score=0.9,
        )
        missing_row2 = SimpleNamespace(
            email="bob@example.com",
            name="Bob User",
            session_id=30,
            peardeck_score=0.7,
        )
        matches = [(missing_row1, 111), (missing_row2, 222)]

        class TwoResult:
            def all(self):
                return matches

        # Stub execute().all() to return our two matches
        mock_postgresql_db.execute.return_value = TwoResult()

        # Stub process_matches to return two moved rows
        moved_row1 = {"email": "alice@example.com", "name": "Alice User", "cti_id": 111}
        moved_row2 = {"email": "bob@example.com", "name": "Bob User", "cti_id": 222}

        def fake_process(db_session, got_matches):
            assert got_matches == matches
            return [moved_row1, moved_row2]

        monkeypatch.setattr(service, "process_matches", fake_process)
        mock_postgresql_db.commit.return_value = None

        response = client.post("/api/students/recover-attendance")
        assert response.status_code == 200

        data = response.json()
        if env == "production":
            assert data == {"status": 200, "moved": 2}
        else:
            assert data["status"] == 200
            assert data["moved"] == 2
            # In development, rows should contain both moved rows
            assert data["rows"] == [moved_row1, moved_row2]

        mock_postgresql_db.commit.assert_called_once()


    @pytest.mark.parametrize("env", ["production", "development"])
    def test_skip_existing_attendance(self, env, monkeypatch, mock_postgresql_db):
        """
        Test the case where a MissingAttendance record exists, but a corresponding
        StudentAttendance already exists for the same cti_id and session_id.
        The endpoint should return moved=0, and in development env rows should be empty.
        """
        monkeypatch.setattr(settings, "app_env", env)

        # Simulate one match, but process_matches returns []
        dummy_row = SimpleNamespace(
            email="bar@example.com",
            name="Bar User",
            session_id=5,
            peardeck_score=0.5,
        )
        matches = [(dummy_row, 456)]

        class OneResult:
            def all(self):
                return matches

    
        mock_postgresql_db.execute.return_value = OneResult()
        # Stub process_matches to return an empty list, simulating no moves
        monkeypatch.setattr(service, "process_matches", lambda db_session, matches: [])

        mock_postgresql_db.commit.return_value = None
        response = client.post("/api/students/recover-attendance")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == 200
        assert data["moved"] == 0

        # In development, rows should be empty, in production it should not be present
        if env == "development":
            assert "rows" in data and data["rows"] == []
        else:
            assert "rows" not in data

        mock_postgresql_db.commit.assert_called_once()


    def test_database_error_raises_500(self, mock_postgresql_db):
        """
        Simulate a database error during the transaction.
            - The endpoint should return HTTP 500.
            - The database rollback should be called.   
        """
        def raise_err(stmt):
            raise SQLAlchemyError("fail")

        mock_postgresql_db.execute.side_effect = raise_err
        mock_postgresql_db.rollback.return_value = None

        response = client.post("/api/students/recover-attendance")
        assert response.status_code == 500

        mock_postgresql_db.rollback.assert_called_once()
