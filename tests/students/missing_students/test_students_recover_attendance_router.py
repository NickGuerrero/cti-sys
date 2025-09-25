import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock
from sqlalchemy.exc import SQLAlchemyError
from src.config import settings
from src.students.missing_students import service

class TestRecoverAttendance:
    def test_no_missing_records(self, client, monkeypatch, mock_postgresql_db, auth_headers):
        """
        Test the case where there are no MissingAttendance records.
        """
        # Stub execute().all() to return an empty list
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_postgresql_db.execute.return_value = mock_result

        # Stub process_matches to return an empty list
        monkeypatch.setattr(service, "process_matches", lambda db_session, matches: [])

        response = client.post("/api/students/recover-attendance", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == {"status": 200, "moved": 0}

        mock_postgresql_db.commit.assert_not_called()

    @pytest.mark.parametrize("env", ["production", "development"])
    def test_move_single_record(self, client, env, monkeypatch, mock_postgresql_db, auth_headers):
        """
        Test the case where there is one match for MissingAttendance.
        The endpoint should return moved=1, and in development env rows 
        should contain the moved row with details like email, name, cti_id.
        """
        monkeypatch.setattr(settings, "app_env", env)

        # Create a fake MissingAttendance row and its cti_id match
        missing_row = SimpleNamespace(email="foo@example.com", name="Foo User", session_id=10, peardeck_score=0.8)
        matches = [(missing_row, 123)]

        # Stub execute().all() to return our single match
        mock_result = MagicMock()
        mock_result.all.return_value = matches
        mock_postgresql_db.execute.return_value = mock_result

        # Stub process_matches to return a moved row
        moved_row = {"email": "foo@example.com", "name": "Foo User", "cti_id": 123}

        def fake_process(db_session, got_matches):
            assert got_matches == matches
            return [moved_row]

        monkeypatch.setattr(service, "process_matches", fake_process)
        mock_postgresql_db.commit = MagicMock()

        response = client.post("/api/students/recover-attendance", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        if env == "production":
            assert data == {"status": 200, "moved": 1}
        else:
            assert data["status"] == 200
            assert data["moved"] == 1
            assert data["rows"] == [moved_row]

        mock_postgresql_db.commit.assert_called_once()

    @pytest.mark.parametrize("env", ["production", "development"])
    def test_move_multiple_records(self, client, env, monkeypatch, mock_postgresql_db, auth_headers):
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

        mock_result = MagicMock()
        mock_result.all.return_value = matches
        mock_postgresql_db.execute.return_value = mock_result

        moved_row1 = {"email": "alice@example.com", "name": "Alice User", "cti_id": 111}
        moved_row2 = {"email": "bob@example.com", "name": "Bob User", "cti_id": 222}

        def fake_process(db_session, got_matches):
            assert got_matches == matches
            return [moved_row1, moved_row2]

        monkeypatch.setattr(service, "process_matches", fake_process)
        mock_postgresql_db.commit = MagicMock()

        response = client.post("/api/students/recover-attendance", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        if env == "production":
            assert data == {"status": 200, "moved": 2}
        else:
            assert data["status"] == 200
            assert data["moved"] == 2
            assert data["rows"] == [moved_row1, moved_row2]

        mock_postgresql_db.commit.assert_called_once()

    @pytest.mark.parametrize("env", ["production", "development"])
    def test_skip_existing_attendance(self, client, env, monkeypatch, mock_postgresql_db, auth_headers):
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

        mock_result = MagicMock()
        mock_result.all.return_value = matches
        mock_postgresql_db.execute.return_value = mock_result

        monkeypatch.setattr(service, "process_matches", lambda db_session, matches: [])
        mock_postgresql_db.commit = MagicMock()

        response = client.post("/api/students/recover-attendance", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == 200
        assert data["moved"] == 0

        if env == "development":
            assert data["rows"] == []
        else:
            assert "rows" not in data

        mock_postgresql_db.commit.assert_called_once()

    def test_database_error_raises_500(self, client, mock_postgresql_db, auth_headers):
        """
        Simulate a database error during the transaction.
        """
        mock_postgresql_db.execute.side_effect = SQLAlchemyError("fail")
        mock_postgresql_db.rollback = MagicMock()

        response = client.post("/api/students/recover-attendance", headers=auth_headers)
        assert response.status_code == 500

        mock_postgresql_db.rollback.assert_called_once()
