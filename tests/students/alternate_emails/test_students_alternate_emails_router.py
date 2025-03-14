from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from src.database.postgres.models import Student, StudentEmail
from src.main import app

client = TestClient(app)

class TestModifyAlternateEmails:
    def test_add_alternate_emails(self, mock_postgresql_db):
        """Test adding alternate emails for a student."""
        student = Student(cti_id=1, fname="Nicolas", lname="Guerrero")
        student_email = StudentEmail(email="ngcti@email.com", cti_id=1, is_primary=True)

        mock_postgresql_db.query.return_value.filter.return_value.first.side_effect = [
            student_email,
            student,
            None,
            None,
        ]

        mock_postgresql_db.query.return_value.filter.return_value.all.return_value = [
            student_email
        ]

        response = client.post("/api/students/alternate-emails", json={
            "alt_emails": ["newemail@email.com", "newemail2@email.com"],
            "google_form_email": "ngcti@email.com"
        })

        assert response.status_code == 200
        assert response.json() == {"status": 200}
    
    def test_add_alternate_email_already_exists(self, mock_postgresql_db):
        """Test adding an alternate email that already belongs to another student."""
        student = Student(cti_id=1, fname="Nicolas", lname="Guerrero")
        student_email = StudentEmail(email="ngcti@email.com", cti_id=1, is_primary=True)
        other_student_email = StudentEmail(email="someoneelse@email.com", cti_id=2, is_primary=True)

        mock_postgresql_db.query.return_value.filter.return_value.first.side_effect = [
            student_email,
            student,    
            other_student_email,
        ]

        mock_postgresql_db.query.return_value.filter.return_value.all.return_value = [student_email]

        response = client.post("/api/students/alternate-emails", json={
            "alt_emails": ["someoneelse@email.com"],
            "google_form_email": "ngcti@email.com",
        })

        assert response.status_code == 403
        assert "already associated with another student" in response.json().get("detail", "")

    def test_student_not_found_by_email(self, mock_postgresql_db):
        """Test where the student email is not found in the database."""
        mock_postgresql_db.query.return_value.filter.return_value.first.return_value = None

        response = client.post("/api/students/alternate-emails", json={
            "alt_emails": ["newalt@email.com"],
            "google_form_email": "notfound@email.com",
        })

        assert response.status_code == 404
        assert "Student not found" in response.json()["detail"]

    def test_remove_alternate_email_success(self, mock_postgresql_db):
        """Test successfully removing an alternate email."""
        student = Student(cti_id=1, fname="Nicolas", lname="Guerrero")
        student_emails = [
            StudentEmail(email="ngcti@email.com", cti_id=1, is_primary=True),
            StudentEmail(email="alt@email.com", cti_id=1, is_primary=False),
        ]

        # Mock database
        mock_postgresql_db.query.return_value.filter.return_value.first.side_effect = [
            student_emails[0], 
            student       
        ]
        mock_postgresql_db.query.return_value.filter.return_value.all.return_value = student_emails

        response = client.post("/api/students/alternate-emails", json={
            "alt_emails": [],
            "remove_emails": ["alt@email.com"],
            "google_form_email": "ngcti@email.com",
        })

        assert response.status_code == 200
        assert response.json() == {"status": 200}

    def test_skip_nonexistent_email_removal(self, mock_postgresql_db):
        """Test that attempting to remove a nonexistent email is silently skipped."""
        student = Student(cti_id=1, fname="Nicolas", lname="Guerrero")
        student_emails = [StudentEmail(email="ngcti@email.com", cti_id=1, is_primary=True)]

        # Mock database 
        mock_postgresql_db.query.return_value.filter.return_value.first.side_effect = [
            student_emails[0],  
            student         
        ]
        mock_postgresql_db.query.return_value.filter.return_value.all.return_value = student_emails

        response = client.post("/api/students/alternate-emails", json={
            "alt_emails": [],
            "remove_emails": ["notfound@email.com"],
            "google_form_email": "ngcti@email.com",
        })

        assert response.status_code == 200
        assert response.json() == {"status": 200}

    def test_primary_email_must_match_form_email(self, mock_postgresql_db):
        """Test that primary_email must match the google_form_email."""
        student = Student(cti_id=1, fname="Nicolas", lname="Guerrero")
        student_emails = [
            StudentEmail(email="ngcti@email.com", cti_id=1, is_primary=True),
            StudentEmail(email="alt@email.com", cti_id=1, is_primary=False)
        ]

        # Mock database
        mock_postgresql_db.query.return_value.filter.return_value.first.side_effect = [
            student_emails[0],  
            student            
        ]
        mock_postgresql_db.query.return_value.filter.return_value.all.return_value = student_emails

        response = client.post("/api/students/alternate-emails", json={
            "alt_emails": [],
            "remove_emails": [],
            "primary_email": "alt@email.com",  # Doesn't match google_form_email
            "google_form_email": "ngcti@email.com",
        })

        assert response.status_code == 403
        assert "Primary email must match the email used to submit the form" in response.json()["detail"]

    def test_add_and_remove_email_together(self, mock_postgresql_db):
        """Test adding a new email and removing an existing one in the same request."""
        student = Student(cti_id=1, fname="Nicolas", lname="Guerrero")
        student_emails = [
            StudentEmail(email="ngcti@email.com", cti_id=1, is_primary=True),
            StudentEmail(email="alt@email.com", cti_id=1, is_primary=False)
        ]

        # Mock database
        mock_postgresql_db.query.return_value.filter.return_value.first.side_effect = [
            student_emails[0],
            student,
            None
        ]
        mock_postgresql_db.query.return_value.filter.return_value.all.return_value = student_emails

        response = client.post("/api/students/alternate-emails", json={
            "alt_emails": ["new@email.com"],
            "remove_emails": ["alt@email.com"],
            "google_form_email": "ngcti@email.com",
        })

        assert response.status_code == 200
        assert response.json() == {"status": 200}

    def test_skip_email_in_both_add_and_remove(self, mock_postgresql_db):
        """Test that an email in both alt_emails and remove_emails is skipped."""
        student = Student(cti_id=1, fname="Nicolas", lname="Guerrero")
        student_emails = [StudentEmail(email="ngcti@email.com", cti_id=1, is_primary=True)]

        # Mock database 
        mock_postgresql_db.query.return_value.filter.return_value.first.side_effect = [
            student_emails[0],
            student
        ]
        mock_postgresql_db.query.return_value.filter.return_value.all.return_value = student_emails

        response = client.post("/api/students/alternate-emails", json={
            "alt_emails": ["new@email.com"],
            "remove_emails": ["new@email.com"],  # Same email in both lists
            "google_form_email": "ngcti@email.com",
        })

        assert response.status_code == 200
        assert response.json() == {"status": 200}

    def test_database_error_handling(self, mock_postgresql_db):
        """Test handling of SQLAlchemy database errors."""
        student = Student(cti_id=1, fname="Nicolas", lname="Guerrero")
        student_email = StudentEmail(email="ngcti@email.com", cti_id=1, is_primary=True)
        
        # Mock database
        mock_postgresql_db.query.return_value.filter.return_value.first.side_effect = [
            student_email, 
            student,
            None
        ]
        
        mock_postgresql_db.query.return_value.filter.return_value.all.return_value = [student_email]
        
        # Simulate database error
        mock_postgresql_db.commit.side_effect = SQLAlchemyError("Database error")

        response = client.post("/api/students/alternate-emails", json={
            "alt_emails": ["newemail@email.com"],
            "remove_emails": [],
            "google_form_email": "ngcti@email.com",
        })

        assert response.status_code == 500
        assert "Database error" in response.json()["detail"]
        assert mock_postgresql_db.rollback.called

    def test_empty_request_validation_fail(self, mock_postgresql_db):
        """Test that an empty request body fails validation."""
        response = client.post("/api/students/alternate-emails", json={})
        assert response.status_code == 422
