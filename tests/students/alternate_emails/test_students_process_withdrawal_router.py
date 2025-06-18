from fastapi.testclient import TestClient
import pytest

from src.database.postgres.models import Student, StudentEmail, InactiveRequest
from src.main import app
from src.config import settings

client = TestClient(app)

class TestProcessWithdrawal:
    # =========================
    # Successful Withdrawal
    # =========================

    @pytest.mark.parametrize("env", ["production", "development"])
    def test_process_withdrawal(self, env, monkeypatch, mock_postgresql_db):
        """Test adding alternate emails for a student."""
        monkeypatch.setattr(settings, "app_env", env)
        primary_email = StudentEmail(email="primary@example.com", cti_id=1, is_primary=True)
        manual_email = StudentEmail(email="manual@example.com", cti_id=1, is_primary=False)
        record = InactiveRequest(passkey=2, id=1, created=3)

        # Lookup and student record fetch.
        mock_postgresql_db.query.return_value.filter.return_value.first.side_effect = [
            primary_email,  # initial primary fetch in find_student_by_google_email
            primary_email,
            record
        ]
        # Simulate before and after modifications.
        mock_postgresql_db.query.return_value.filter.return_value.all.side_effect = [
            [primary_email, manual_email]
        ]
        query = mock_postgresql_db.query.return_value.filter.return_value
        query.add.return_value = 1
        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.rollback.return_value = None

        response = client.post("/api/students/process-withdrawal", json={
            "auto_email": primary_email.email,
            "fname": "Jane",
            "lname": "Doe"
        })

        assert response.status_code == 200
        data = response.json()
        if env == "production":
            assert data == {"status": 200}
        else:
            assert data["status"] == 200
            assert "id" in data
            assert "passkey" in data
            assert "timestamp" in data
            assert data["id"] == record.id
            assert data["passkey"] == record.passkey
            assert data["timestamp"] == record.created
        
    # # ====================
    # # Error Conditions
    # # ====================
    @pytest.mark.parametrize("env", ["production", "development"])
    def test_process_withdrawal_mistmatch_email(self, env, monkeypatch, mock_postgresql_db):
        """Test adding alternate emails for a student."""
        monkeypatch.setattr(settings, "app_env", env)
        student = Student(cti_id=1, fname="Jane", lname="Doe")
        primary_email = StudentEmail(email="primary@example.com", cti_id=1, is_primary=True)
        nonprimary_email = StudentEmail(email="manual@example.com", cti_id=1, is_primary=False)
        record = InactiveRequest(passkey=2, id=1, created=3)

        # Lookup and student record fetch.
        mock_postgresql_db.query.return_value.filter.return_value.first.side_effect = [
            nonprimary_email,  # initial primary fetch in find_student_by_google_email
            primary_email,
            record
        ]
        # Simulate before and after modifications.
        mock_postgresql_db.query.return_value.filter.return_value.all.side_effect = [
            [primary_email, nonprimary_email]
        ]
        query = mock_postgresql_db.query.return_value.filter.return_value
        query.add.return_value = 1
        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.rollback.return_value = None

        response = client.post("/api/students/process-withdrawal", json={
            "auto_email": nonprimary_email.email,
            "fname": "Jane",
            "lname": "Doe"
        })

        assert response.status_code == 403
        detail = response.json().get("detail", "")
        assert "Primary email must match the email used to submit the form." in detail