from datetime import datetime, timezone
import os
import bson
import pymongo
import pymongo.client_session
import pymongo.database
import pymongo.errors
import pymongo.mongo_client
import pytest
import mongomock
from fastapi.testclient import TestClient
from src.app.models.mongo.models import ApplicationModel
from src.app.models.mongo.schemas import init_collections
from src.config import APPLICATIONS_COLLECTION, MONGO_DATABASE_NAME
from src.db_scripts.mongo import get_mongo
from src.main import app
from sqlalchemy.orm import Session
from unittest.mock import MagicMock
from src.app.database import make_session
from src.app.models.postgres.models import Student, StudentEmail

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "cti-sys v1.0.0"}

def test_confirm_conn():
    response = client.get("/test-connection")
    assert response.status_code == 200
    assert response.json() == {"message": "Database connection succeeded"}

@pytest.fixture(scope="function")
def mock_mongo_db():
    """Injection for MongoDB dependency intended for fast, in-memory unit testing"""
    mock_client = mongomock.MongoClient()
    db = mock_client[MONGO_DATABASE_NAME]

    # Apply indexes (json schema validators cannot be enforced in mongomock)
    init_collections(db, with_validators=False)

    # Override FastAPI's database dependency
    app.dependency_overrides[get_mongo] = lambda: db

    yield db # Provide the mock DB instance

    app.dependency_overrides.pop(get_mongo) # Clean up override(s) after test
    mock_client.close()

@pytest.fixture(scope="function")
def real_mongo_db():
    """Injection for MongoDB dependency intended for wide scope, accurate integration testing"""
    # Consider replacing this with a conditionally created local instance (in GitHub Actions)
    client = pymongo.MongoClient(os.environ.get("CTI_MONGO_URL"))
    test_db_name = "test_" + MONGO_DATABASE_NAME
    db = client[test_db_name]
    init_collections(db, with_validators=True)

    app.dependency_overrides[get_mongo] = lambda: db

    yield db

    app.dependency_overrides.pop(get_mongo)
    client.drop_database(db)
    client.close()

class TestCreateApplication:
    def test_success_min_required_fields(self, mock_mongo_db: mongomock.Database):
        response = client.post("/api/applications", json={
            "fname": "First",
            "lname": "Last",
            "email": "test.user@cti.com"
        })

        assert response.status_code == 201
        assert bson.ObjectId.is_valid(response.json()["_id"])

    def test_success_with_extra_fields(self, mock_mongo_db: mongomock.Database):
        response = client.post("/api/applications", json={
            "fname": "First",
            "lname": "Last",
            "email": "test.user@cti.com",
            "cohort": True,
            "graduating_year": 2024
        })

        assert response.status_code == 201
        assert bson.ObjectId.is_valid(response.json()["_id"])
        assert response.json()["cohort"]
        assert response.json()["graduating_year"] == 2024

    def test_failure_missing_required_last_name(self, mock_mongo_db: mongomock.Database):
        response = client.post("/api/applications", json={
            "fname": "First",
            # missing lname
            "email": "test.user@cti.com",
            "cohort": True,
            "graduating_year": 2024
        })

        assert response.status_code == 422
        detail = response.json()["detail"][0]
        assert detail["type"] == "missing"

    def test_failure_invalid_email(self, mock_mongo_db: mongomock.Database):
        response = client.post("/api/applications", json={
            "fname": "First",
            "lname": "Last",
            "email": "test.user@cti",
            "cohort": True,
            "graduating_year": 2024
        })

        assert response.status_code == 422
        detail = response.json()["detail"][0]
        assert detail["type"] == "value_error"
        assert "not a valid email address" in detail["msg"]

    def test_failure_duplicate_email_key(self, mock_mongo_db: mongomock.Database):
        # pydantic model used to validate test data before inserting as mongomock does not support json schema validation
        app = ApplicationModel(
            fname="First",
            lname="Last",
            email="test.user@cti.com", # email is a unique index
            cohort=True,
            graduating_year=2024,
            app_submitted=datetime.now(timezone.utc)
        )
        
        mock_mongo_db.get_collection(APPLICATIONS_COLLECTION).insert_one(app.model_dump())
        
        response = client.post("/api/applications", json={
            "fname": "First",
            "lname": "Last",
            "email": "test.user@cti.com",
            "cohort": True,
            "graduating_year": 2024
        })

        assert response.status_code == 409
        detail = response.json()["detail"]
        assert "Duplicate index key" in detail

    @pytest.mark.integration
    def test_application_persistence(self, real_mongo_db: pymongo.database.Database):
        """Integration test validating that a document can be inserted and found
        if the fields follow the collection schema
        """
        app_collection = real_mongo_db.get_collection(APPLICATIONS_COLLECTION)
        prev_count = app_collection.count_documents({})

        response = client.post("/api/applications", json={
            "fname": "First",
            "lname": "Last",
            "email": "test.user@cti.com"
        })

        inserted = app_collection.find_one({"email": "test.user@cti.com"})

        assert response.status_code == 201
        assert bson.ObjectId.is_valid(response.json()["_id"])
        assert inserted is not None and str(inserted["_id"]) == response.json()["_id"]
        assert prev_count + 1 == app_collection.count_documents({})
    
    @pytest.mark.integration
    def test_application_schema_rejects_invalid_insert(self, real_mongo_db: pymongo.database.Database):
        """Integration test validating that a document will not be inserted
        if it does not follow the collection json validation schema.
        
        Relevant for inserts performed outside of API.
        """
        app_collection = real_mongo_db.get_collection(APPLICATIONS_COLLECTION)

        with pytest.raises(pymongo.errors.WriteError, match="Document failed validation"):
            app_collection.insert_one({
                "fname": "First",
                "lname": "Last",
                "email": "test.user@cti.com"
                # missing app_submitted
            })

@pytest.fixture(scope="function")
def mock_postgresql_db():
    """Fixture to mock a PostgreSQL database session for testing."""
    db = MagicMock(spec=Session)
    app.dependency_overrides[make_session] = lambda: db
    yield db
    app.dependency_overrides.pop(make_session)

class TestModifyAlternateEmails:
    
    def test_add_alternate_emails(self, mock_postgresql_db):
        """Test adding alternate emails for a student."""
        student_email = [StudentEmail(email="ngcti@email.com", cti_id=1, is_primary=True)]
        
        # Mock database response for existing student email
        mock_postgresql_db.query.return_value.filter.return_value.all.return_value = student_email

        response = client.post("/api/students/alternate-emails", json={
            "fname": "Nicolas",
            "lname": "Guerrero",
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

        # Mock database responses for email checks
        mock_postgresql_db.query.return_value.filter.return_value.first.side_effect = [
            student_email,
            student, 
            other_student_email,
        ]

        mock_postgresql_db.query.return_value.filter.return_value.all.return_value = [student_email]

        response = client.post("/api/students/alternate-emails", json={
            "fname": "Nicolas",
            "lname": "Guerrero",
            "alt_emails": ["someoneelse@email.com"],
            "google_form_email": "ngcti@email.com"
        })

        assert response.status_code == 403
        assert "already associated with another student" in response.json().get("detail", "")

    def test_set_existing_alternate_as_primary(self, mock_postgresql_db):
        """Test setting an existing alternate email as the primary email."""
        student_email = StudentEmail(email="ngcti@email.com", cti_id=1, is_primary=True)
        alt_email = StudentEmail(email="alt@email.com", cti_id=1, is_primary=False)

        # Mock database response for existing student emails
        mock_postgresql_db.query.return_value.filter.return_value.all.return_value = [
            student_email,
            alt_email,
        ]

        response = client.post("/api/students/alternate-emails", json={
            "fname": "Nicolas",
            "lname": "Guerrero",
            "primary_email": "alt@email.com",
            "google_form_email": "ngcti@email.com"
        })

        assert response.status_code == 200

    def test_add_alternate_and_set_as_primary(self, mock_postgresql_db):
        """Test adding an alternate email and setting it as primary at the same time."""
        student_email = [StudentEmail(email="ngcti@email.com", cti_id=1, is_primary=True)]

        # Mock database response for existing student emails
        mock_postgresql_db.query.return_value.filter.return_value.all.return_value = student_email

        response = client.post("/api/students/alternate-emails", json={
            "fname": "Nicolas",
            "lname": "Guerrero",
            "alt_emails": ["newprimary@email.com"],
            "primary_email": "newprimary@email.com",
            "google_form_email": "ngcti@email.com"
        })

        assert response.status_code == 200

    def test_set_invalid_primary_email(self, mock_postgresql_db):
        """Test setting an invalid email as primary (not associated with the student)."""
        student_email = StudentEmail(email="ngcti@email.com", cti_id=1, is_primary=True)
        alt_email = StudentEmail(email="alt@email.com", cti_id=1, is_primary=False)

        # Mock database response for existing student emails
        mock_postgresql_db.query.return_value.filter.return_value.all.return_value = [
            student_email,
            alt_email,
        ]

        response = client.post("/api/students/alternate-emails", json={
            "fname": "Nicolas",
            "lname": "Guerrero",
            "primary_email": "notregistered@email.com",
            "google_form_email": "ngcti@email.com"
        })

        assert response.status_code == 403
        assert "Primary email must be an existing or newly added student email" in response.json()["detail"]

    def test_cannot_remove_primary_email(self, mock_postgresql_db):
        """Test that attempting to remove the primary email results in an error."""
        student_emails = [
            StudentEmail(email="ngcti@email.com", cti_id=1, is_primary=True),
            StudentEmail(email="alt@email.com", cti_id=1, is_primary=False),
            StudentEmail(email="alt2@email.com", cti_id=1, is_primary=False)
        ]

        # Mock database response for existing student emails
        mock_postgresql_db.query.return_value.filter.return_value.all.return_value = student_emails
        mock_postgresql_db.query.return_value.filter.return_value.first.return_value = student_emails[0]

        response = client.post("/api/students/alternate-emails", json={
            "fname": "Nicolas",
            "lname": "Guerrero",
            "remove_emails": ["ngcti@email.com"],
            "google_form_email": "ngcti@email.com"
        })

        assert response.status_code == 403
        assert "Cannot remove primary email" in response.json()["detail"]

    def test_remove_alternate_email_success(self, mock_postgresql_db):
        """Test successfully removing an alternate email."""
        student_emails = [
            StudentEmail(email="ngcti@email.com", cti_id=1, is_primary=True),
            StudentEmail(email="alt@email.com", cti_id=1, is_primary=False),
        ]

        # Mock database response for existing student emails
        mock_postgresql_db.query.return_value.filter.return_value.all.return_value = student_emails

        response = client.post("/api/students/alternate-emails", json={
            "fname": "Nicolas",
            "lname": "Guerrero",
            "remove_emails": ["alt@email.com"],
            "google_form_email": "ngcti@email.com"
        })

        assert response.status_code == 200
        assert response.json() == {"status": 200}

    def test_remove_nonexistent_alternate_email(self, mock_postgresql_db):
        """Test removing an alternate email that does not exist in the student record."""
        student_emails = [StudentEmail(email="ngcti@email.com", cti_id=1, is_primary=True)]

        # Mock database response for existing student emails
        mock_postgresql_db.query.return_value.filter.return_value.all.return_value = student_emails

        response = client.post("/api/students/alternate-emails", json={
            "fname": "Nicolas",
            "lname": "Guerrero",
            "remove_emails": ["notfound@email.com"],
            "google_form_email": "ngcti@email.com"
        })

        assert response.status_code == 400
        assert "not found in student record" in response.json()["detail"]

    def test_student_not_found(self, mock_postgresql_db):
        """Test where the student is not found in the database."""
        mock_postgresql_db.query.return_value.filter.return_value.first.return_value = None

        response = client.post("/api/students/alternate-emails", json={
            "fname": "John",
            "lname": "Doe",
            "alt_emails": ["newalt@email.com"],
            "google_form_email": "ngcti@email.com"
        })

        assert response.status_code == 404
        assert "Student not found" in response.json()["detail"]

    def test_empty_request_validation_fail(self, mock_postgresql_db):
        """Test that an empty request body fails validation."""
        response = client.post("/api/students/alternate-emails", json={})
        assert response.status_code == 422
