from fastapi.testclient import TestClient
import pytest

from src.database.postgres.models import Student, StudentEmail
from src.main import app
from src.config import settings

client = TestClient(app)

class TestModifyAlternateEmails:
    # =========================
    # Successful Modifications
    # =========================

    @pytest.mark.parametrize("env", ["production", "development"])
    def test_add_alternate_emails(self, env, monkeypatch, mock_postgresql_db):
        """Test adding alternate emails for a student."""
        monkeypatch.setattr(settings, "app_env", env)
        student = Student(cti_id=1, fname="Jane", lname="Doe")
        primary_email = StudentEmail(email="primary@example.com", cti_id=1, is_primary=True)
        new_email_1 = StudentEmail(email="new1@example.com", cti_id=1, is_primary=False)
        new_email_2 = StudentEmail(email="new2@example.com", cti_id=1, is_primary=False)

        # Lookup and student record fetch.
        mock_postgresql_db.query.return_value.filter.return_value.first.side_effect = [
            primary_email,  # initial primary fetch in find_student_by_google_email
            student,        # student record lookup
            None,           # new_email_1 not found
            None,           # new_email_2 not found
            primary_email   # final fetch in fetch_current_emails
        ]
        # Simulate before and after modifications.
        mock_postgresql_db.query.return_value.filter.return_value.all.side_effect = [
            [primary_email],
            [primary_email, new_email_1, new_email_2]
        ]
        query = mock_postgresql_db.query.return_value.filter.return_value
        query.update.return_value = 1
        query.delete.return_value = 1
        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.rollback.return_value = None

        response = client.post("/api/students/alternate-emails", json={
            "alt_emails": [new_email_1.email, new_email_2.email],
            "google_form_email": primary_email.email,
            "primary_email": primary_email.email
        })

        assert response.status_code == 200
        data = response.json()
        if env == "production":
            assert data == {"status": 200}
        else:
            assert data["status"] == 200
            assert "emails" in data and "primary_email" in data
            emails_lower = [e.lower() for e in data["emails"]]
            assert new_email_1.email.lower() in emails_lower
            assert new_email_2.email.lower() in emails_lower
            assert data["primary_email"].lower() == primary_email.email.lower()

    @pytest.mark.parametrize("env", ["production", "development"])
    def test_remove_alternate_email_success(self, env, monkeypatch, mock_postgresql_db):
        """Test successfully removing an alternate email."""
        monkeypatch.setattr(settings, "app_env", env)
        student = Student(cti_id=1, fname="Jane", lname="Doe")
        primary = StudentEmail(email="ngcti@email.com", cti_id=1, is_primary=True)
        alternate = StudentEmail(email="alt@email.com", cti_id=1, is_primary=False)

        # Lookup and student record fetch.
        mock_postgresql_db.query.return_value.filter.return_value.first.side_effect = [
            primary,  # find_student_by_google_email
            student,  # student record
            primary   # update_primary_email later
        ]
        # First call returns both emails, second call returns only the primary.
        mock_postgresql_db.query.return_value.filter.return_value.all.side_effect = [
            [primary, alternate],
            [primary]
        ]
        query = mock_postgresql_db.query.return_value.filter.return_value
        query.update.return_value = 1
        query.delete.return_value = 1
        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.rollback.return_value = None

        response = client.post("/api/students/alternate-emails", json={
            "alt_emails": [],
            "remove_emails": [alternate.email],
            "google_form_email": primary.email,
            "primary_email": primary.email
        })

        assert response.status_code == 200
        data = response.json()
        if env == "production":
            assert data == {"status": 200}
        else:
            emails_lower = [e.lower() for e in data["emails"]]
            assert primary.email.lower() in emails_lower
            assert data["primary_email"].lower() == primary.email.lower()

    @pytest.mark.parametrize("env", ["production", "development"])
    def test_update_primary_email(self, env, monkeypatch, mock_postgresql_db):
        """
        Test changing the primary email without removing any emails.
        Initially, the student has 'old@example.com' as primary and 'new@example.com' as an alternate.
        The request changes the primary email to 'new@example.com'.
        """
        monkeypatch.setattr(settings, "app_env", env)
        student = Student(cti_id=1, fname="Jane", lname="Doe")
        old_email = StudentEmail(email="old@example.com", cti_id=1, is_primary=True)
        new_email = StudentEmail(email="new@example.com", cti_id=1, is_primary=False)

        # Lookup and student record fetch.
        mock_postgresql_db.query.return_value.filter.return_value.first.side_effect = [
            new_email,  # lookup by google_form_email returns the alternate
            student,    # fetch student record
            new_email   # fetch_current_emails returns new_email as primary
        ]
        # new_email is now primary and old_email remains non primary.
        updated_old_email = StudentEmail(email="old@example.com", cti_id=1, is_primary=False)
        updated_new_email = StudentEmail(email="new@example.com", cti_id=1, is_primary=True)
        mock_postgresql_db.query.return_value.filter.return_value.all.return_value = [
            updated_old_email, updated_new_email
        ]
        query = mock_postgresql_db.query.return_value.filter.return_value
        query.update.side_effect = [1, 1]
        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.rollback.return_value = None

        response = client.post("/api/students/alternate-emails", json={
            "alt_emails": [],
            "remove_emails": [],
            "google_form_email": new_email.email,
            "primary_email": new_email.email
        })

        assert response.status_code == 200
        data = response.json()
        if env == "production":
            assert data == {"status": 200}
        else:
            assert data["status"] == 200
            assert "emails" in data
            emails_lower = [e.lower() for e in data["emails"]]
            # Verify both emails remain and primary is updated.
            assert old_email.email.lower() in emails_lower
            assert new_email.email.lower() in emails_lower
            assert data["primary_email"].lower() == new_email.email.lower()

    # ====================
    # Error Conditions
    # ====================

    def test_add_alternate_email_already_exists(self, monkeypatch, mock_postgresql_db):
        """Test error when an alternate email is already associated with another student."""
        student = Student(cti_id=1, fname="Jane", lname="Doe")
        student_email = StudentEmail(email="ngcti@email.com", cti_id=1, is_primary=True)
        other_student_email = StudentEmail(email="someoneelse@email.com", cti_id=2, is_primary=True)

        mock_postgresql_db.query.return_value.filter.return_value.first.side_effect = [
            student_email,      # student's email record found
            student,            # student record found
            other_student_email # alternate email belongs to another student
        ]
        mock_postgresql_db.query.return_value.filter.return_value.all.return_value = [student_email]

        response = client.post("/api/students/alternate-emails", json={
            "alt_emails": [other_student_email.email],
            "google_form_email": student_email.email,
            "primary_email": student_email.email
        })

        assert response.status_code == 403
        detail = response.json().get("detail", "")
        assert "already associated with another student" in detail

    def test_student_not_found_by_email(self, monkeypatch, mock_postgresql_db):
        """Test error when no student is found for the given Google Form email."""
        mock_postgresql_db.query.return_value.filter.return_value.first.return_value = None

        response = client.post("/api/students/alternate-emails", json={
            "alt_emails": ["newalt@email.com"],
            "google_form_email": "notfound@email.com",
            "primary_email": "notfound@email.com"
        })

        assert response.status_code == 404
        assert "Student not found" in response.json().get("detail", "")

    def test_primary_email_must_match_form_email(self, monkeypatch, mock_postgresql_db):
        """Test error when provided primary email does not match the email used in the form."""
        student = Student(cti_id=1, fname="Jane", lname="Doe")
        primary = StudentEmail(email="ngcti@email.com", cti_id=1, is_primary=True)
        alternate = StudentEmail(email="alt@email.com", cti_id=1, is_primary=False)

        mock_postgresql_db.query.return_value.filter.return_value.first.side_effect = [
            primary,  # returns student's primary email
            student   # returns student record
        ]
        mock_postgresql_db.query.return_value.filter.return_value.all.return_value = [primary, alternate]

        response = client.post("/api/students/alternate-emails", json={
            "alt_emails": [],
            "remove_emails": [],
            "primary_email": alternate.email,
            "google_form_email": primary.email
        })

        assert response.status_code == 403
        assert "Primary email must match the email used to submit the form" in response.json().get("detail", "")

    def test_skip_nonexistent_email_removal(self, monkeypatch, mock_postgresql_db):
        """Test that removal skips emails not found in the student record."""
        monkeypatch.setattr(settings, "app_env", "development")
        student = Student(cti_id=1, fname="Jane", lname="Doe")
        primary = StudentEmail(email="ngcti@email.com", cti_id=1, is_primary=True)
        alt = StudentEmail(email="alt@email.com", cti_id=1, is_primary=False)

        mock_postgresql_db.query.return_value.filter.return_value.first.side_effect = [
            primary,  # primary lookup
            student,  # student record
            primary   # for update_primary_email
        ]
        mock_postgresql_db.query.return_value.filter.return_value.all.side_effect = [
            [primary, alt],
            [primary]
        ]
        query = mock_postgresql_db.query.return_value.filter.return_value
        query.update.return_value = 1
        query.delete.return_value = 1
        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.rollback.return_value = None

        response = client.post("/api/students/alternate-emails", json={
            "alt_emails": [],
            "remove_emails": ["notfound@email.com", alt.email],
            "google_form_email": primary.email,
            "primary_email": primary.email
        })

        assert response.status_code == 200
        data = response.json()
        if settings.app_env == "production":
            assert data == {"status": 200}
        else:
            emails_lower = [e.lower() for e in data["emails"]]
            assert primary.email.lower() in emails_lower
            assert alt.email.lower() not in emails_lower
            assert data["primary_email"].lower() == primary.email.lower()

    def test_remove_primary_email_without_new_primary(self, monkeypatch, mock_postgresql_db):
        """
        Test error when attempting to remove the primary email without specifying a new primary.
        """
        student = Student(cti_id=1, fname="Jane", lname="Doe")
        primary = StudentEmail(email="primary@example.com", cti_id=1, is_primary=True)

        mock_postgresql_db.query.return_value.filter.return_value.first.side_effect = [
            primary,  # primary email record
            student   # student record
        ]
        mock_postgresql_db.query.return_value.filter.return_value.all.return_value = [primary]

        response = client.post("/api/students/alternate-emails", json={
            "alt_emails": [],
            "remove_emails": [primary.email],
            "google_form_email": primary.email,
            "primary_email": ""
        })

        assert response.status_code == 403
        assert "Cannot remove primary email" in response.json().get("detail", "")

    def test_update_primary_email_not_found(self, monkeypatch, mock_postgresql_db):
        """
        Test error when update for setting a new primary email fails.
        """
        student = Student(cti_id=1, fname="Jane", lname="Doe")
        primary = StudentEmail(email="primary@example.com", cti_id=1, is_primary=False)

        mock_postgresql_db.query.return_value.filter.return_value.first.side_effect = [
            primary,  # lookup returns primary email record
            student   # student record lookup
        ]
        mock_postgresql_db.query.return_value.filter.return_value.all.return_value = [primary]
        query = mock_postgresql_db.query.return_value.filter.return_value
        query.update.side_effect = [1, 0]
        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.rollback.return_value = None

        response = client.post("/api/students/alternate-emails", json={
            "alt_emails": [],
            "remove_emails": [],
            "google_form_email": primary.email,
            "primary_email": primary.email
        })

        assert response.status_code == 404
        assert f"Could not set '{primary.email}' as primary" in response.json().get("detail", "")
