from unittest.mock import MagicMock
from sqlalchemy.exc import SQLAlchemyError
from src.students import withdrawal_processing as module

class TestProcessWithdrawal:
    def test_student_not_found(self, client, mock_postgresql_db, monkeypatch):
        """
        Simulate a scenario where the student email does not exist.
        """
        fake_result = {"status": 404, "message": "No student found with email: missing@example.com"}
        monkeypatch.setattr(module.router, "process_withdrawal_form", lambda db, email: fake_result)
        mock_postgresql_db.commit = MagicMock()

        response = client.post("/api/students/process-withdrawal", json={"email": "missing@example.com"})
        assert response.status_code == 200
        assert response.json() == fake_result
        mock_postgresql_db.commit.assert_called_once()

    def test_successful_deactivation(self, client, mock_postgresql_db, monkeypatch):
        """
        Test a normal case where Student and Accelerate records are deactivated.
        """
        fake_result = {
            "status": 200,
            "message": "Student John Doe (CTI ID: 101) and all related records have been deactivated.",
            "email": "john.doe@example.com",
        }

        def fake_service(db, email):
            assert email == "john.doe@example.com"
            return fake_result

        monkeypatch.setattr(module.router, "process_withdrawal_form", fake_service)
        mock_postgresql_db.commit = MagicMock()

        response = client.post("/api/students/process-withdrawal", json={"email": "john.doe@example.com"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == 200
        assert "deactivated" in data["message"]
        mock_postgresql_db.commit.assert_called_once()

    def test_invalid_student_record(self, client, mock_postgresql_db, monkeypatch):
        """
        Test when the email exists but no associated Student record is found.
        """
        fake_result = {"status": 404, "message": "No student record found for email: test@example.com"}
        monkeypatch.setattr(module.router, "process_withdrawal_form", lambda db, email: fake_result)
        mock_postgresql_db.commit = MagicMock()

        response = client.post("/api/students/process-withdrawal", json={"email": "test@example.com"})
        assert response.status_code == 200
        assert response.json() == fake_result
        mock_postgresql_db.commit.assert_called_once()

    def test_database_error_raises_500(self, client, mock_postgresql_db):
        """
        Simulate a database error during the withdrawal process.
        """
        mock_postgresql_db.execute.side_effect = SQLAlchemyError("db failure")
        mock_postgresql_db.rollback = MagicMock()

        response = client.post("/api/students/process-withdrawal", json={"email": "error@example.com"})
        assert response.status_code == 500
        mock_postgresql_db.rollback.assert_called_once()
