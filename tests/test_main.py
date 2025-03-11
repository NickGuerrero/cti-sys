from datetime import datetime, timezone
import os
import bson
from pydantic import ValidationError
import pymongo
import pymongo.client_session
import pymongo.database
import pymongo.errors
import pymongo.mongo_client
import pytest
import mongomock
from fastapi.testclient import TestClient
from src.config import ACCELERATE_FLEX_COLLECTION, APPLICATIONS_COLLECTION, COURSES_COLLECTION, MONGO_DATABASE_NAME, PATHWAY_GOALS_COLLECTION
from src.database.mongo.core import get_mongo
from src.database.mongo.services import init_collections
from src.database.mongo.tmp_schemas import AccelerateFlexBase, ApplicationModel, CourseBase, DeepWork, PathwayGoalBase
from src.database.postgres.core import make_session
from src.database.postgres.models import Student, StudentEmail
from src.main import app
from sqlalchemy.orm import Session
from unittest.mock import MagicMock
from sqlalchemy.exc import SQLAlchemyError


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

class TestAccelerateFlex:
    @pytest.mark.parametrize("data", [
        # Required field(s) only
        {"cti_id": 100},

        # With optional nested data structure(s)
        {"cti_id": 100, "selected_deep_work": [{"day": "Friday", "time": "2-4pm", "sprint": "Spring 2024"}], "phone": "(800) 123-4567"},

        # With extra fields (should be ignored on Model construction)
        {"cti_id": 100, "selected_deep_work": [{"day": "Friday", "time": "2-4pm", "sprint": "Spring 2024"}], "phone": "(800) 123-4567", "extra_here": True},
    ])
    def test_accelerate_flex_model_valid_cases(self, data):
        AccelerateFlexBase(**data) # using Base model here rather than Model as not testing DB find result (pre-insert validation)
    
    def test_accelerate_flex_model_provides_none_values(self):
        """Test validates that a value of None is assigned to each property where that non-required, optional field is not provided
        
        Fields of default None value (unset on model creation) can be ignored and not inserted on document
        db inserts by using `collection.insert_one(model.model_dump(exclude_unset=True))`
        """
        cti_id = 100
        phone = "(800) 123-4567"
        model = AccelerateFlexBase(**{
            "cti_id": cti_id,
            "phone": phone
        })

        assert model.career_outlook == None
        assert model.selected_deep_work == None
        assert model.cti_id == cti_id

    @pytest.mark.parametrize("data", [
        # Missing required field(s)
        {},
        
        # Incorrect type
        {"cti_id": 100, "phone": 8001234567}
    ])
    def test_accelerate_flex_model_invalid_cases(self, data):
        with pytest.raises(ValidationError):
            AccelerateFlexBase(**data) # using Base model here rather than Model as not testing DB find result (pre-insert validation)

    @pytest.mark.integration
    def test_accelerate_flex_schema_rejects_invalid_insert(self, real_mongo_db: pymongo.database.Database):
        """Integration test validating that an accelerate_flex document will not be inserted
        if it does not follow the collection json validation schema.
        
        Relevant for inserts performed outside of API.
        """
        accelerate_flex_collection = real_mongo_db.get_collection(ACCELERATE_FLEX_COLLECTION)

        with pytest.raises(pymongo.errors.WriteError, match="Document failed validation"):
            accelerate_flex_collection.insert_one({
                # missing "cti_id": 12345,
                "selected_deep_work": DeepWork(
                    day="Monday",
                    time="2pm - 4pm",
                    sprint="Spring 2024"
                ).model_dump(),
                "academic_goals": ["Bachelor's Degree", "Associate's Degree"],
                "phone": "(800) 123-4567",
                "academic_year": "Sophomore",
                "grad_year": 2027,
                "summers_left": 2,
                "cs_exp": False,
                "cs_courses": ["Data Structures", "Algorithms"],
                "math_courses": ["Calculus 1A", "Discrete Math"],
                "program_expectation": "Summer tech internship",
                "career_outlook": "Graduated and in the workforce",
                "heard_about": "Instructor/Professor",
            })
            
    @pytest.mark.integration
    def test_accelerate_flex_schema_accepts_valid_insert(self, real_mongo_db: pymongo.database.Database):
        """Integration test validating that an accelerate_flex document will be inserted
        if it follows the collection json validation schema.
        """
        accelerate_flex_collection = real_mongo_db.get_collection(ACCELERATE_FLEX_COLLECTION)
        prev_count = accelerate_flex_collection.count_documents({})
        cti_id = 12345

        # todo: upon a POST /api/accelerate-flex endpoint creation, this direct insert can be replaced with a TestClient call
        insert_result = accelerate_flex_collection.insert_one({
            "cti_id": cti_id,
            "selected_deep_work": DeepWork(
                day="Monday",
                time="2pm - 4pm",
                sprint="Spring 2024"
            ).model_dump(),
            "academic_goals": ["Bachelor's Degree", "Associate's Degree"],
            "phone": "(800) 123-4567",
            "academic_year": "Sophomore",
            "grad_year": 2027,
            "summers_left": 2,
            "cs_exp": False,
            "cs_courses": ["Data Structures", "Algorithms"],
            "math_courses": ["Calculus 1A", "Discrete Math"],
            "program_expectation": "Summer tech internship",
            "career_outlook": "Graduated and in the workforce",
            "heard_about": "Instructor/Professor",
        })

        assert insert_result.acknowledged

        found_accelerate_flex = accelerate_flex_collection.find_one({"_id": insert_result.inserted_id})
        assert found_accelerate_flex is not None
        assert found_accelerate_flex["cti_id"] == cti_id
        assert prev_count + 1 == accelerate_flex_collection.count_documents({})

class TestPathwayGoals:
    @pytest.mark.parametrize("data", [
        # Required field(s) only
        {"pathway_goal": "Summer Tech Internship 2025"},

        # With optional field(s)
        {"pathway_goal": "Summer Tech Internship 2025", "course_req": ["101A", "202"]},
    ])
    def test_pathway_goal_model_valid_cases(self, data):
        PathwayGoalBase(**data) # using Base model here rather than Model as not testing DB find result (pre-insert validation)
    
    def test_pathway_goal_model_provides_none_values(self):
        """Test validates that a value of None is assigned to each property where that non-required, optional field is not provided
        
        Fields of default None value (unset on model creation) can be ignored and not inserted on document
        db inserts by using `collection.insert_one(model.model_dump(exclude_unset=True))`
        """
        pathway_goal = "Summer Tech Internship 2025"
        model = PathwayGoalBase(**{
            "pathway_goal": pathway_goal,
        })

        assert model.course_req == None
        assert model.pathway_desc == None
        assert model.pathway_goal == pathway_goal

    @pytest.mark.parametrize("data", [
        # Missing required field(s)
        {},
        
        # Extra field provided
        {"pathway_goal": "Summer Tech Internship 2025", "not_meant_to_be_here": "here"},

        # Incorrect type
        {"pathway_goal": "Summer Tech Internship 2025", "pathway_desc": ["should not be list"]}
    ])
    def test_pathway_goal_model_invalid_cases(self, data):
        with pytest.raises(ValidationError):
            PathwayGoalBase(**data) # using Base model here rather than Model as not testing DB find result (pre-insert validation)

    @pytest.mark.integration
    def test_pathway_goals_schema_rejects_invalid_insert(self, real_mongo_db: pymongo.database.Database):
        """Integration test validating that a pathway_goals document will not be inserted
        if it does not follow the collection json validation schema.
        
        Relevant for inserts performed outside of API.
        """
        pathway_goals_collection = real_mongo_db.get_collection(PATHWAY_GOALS_COLLECTION)

        with pytest.raises(pymongo.errors.WriteError, match="Document failed validation"):
            pathway_goals_collection.insert_one({
                "pathway_goal": "Summer Tech Internship 2025",
                "pathway_desc": "Obtain a summer tech internship for 2025",
                "course_req": "101A" # needs to be an array of strings
            })

    @pytest.mark.integration
    def test_pathway_goals_schema_accepts_valid_insert(self, real_mongo_db: pymongo.database.Database):
        """Integration test validating that a pathway_goals document will be inserted
        if it follows the collection json validation schema.
        """
        pathway_goals_collection = real_mongo_db.get_collection(PATHWAY_GOALS_COLLECTION)
        prev_count = pathway_goals_collection.count_documents({})
        pathway_goal = "Summer Tech Internship 2025"
        pathway_desc = "Obtain a summer tech internship for 2025"
        course_req = ["101A", "202A"]

        # todo: upon a POST /api/pathway-goals endpoint creation, this direct insert can be replaced with a TestClient call
        insert_result = pathway_goals_collection.insert_one({
            "pathway_goal": pathway_goal,
            "pathway_desc": pathway_desc,
            "course_req": course_req
        })

        assert insert_result.acknowledged

        found_pathway_goal = pathway_goals_collection.find_one({"_id": insert_result.inserted_id})
        assert found_pathway_goal is not None
        assert found_pathway_goal["pathway_goal"] == pathway_goal
        assert prev_count + 1 == pathway_goals_collection.count_documents({})

class TestCourses:
    @pytest.mark.parametrize("data", [
        # Required field(s) only
        {"course_id": "101"},

        # With optional field(s)
        {"course_id": "101", "canvas_id": 1234, "title": "Introduction to Problem Solving"},
    ])
    def test_course_model_valid_cases(self, data):
        CourseBase(**data) # using Base model here rather than Model as not testing DB find result (pre-insert validation)
    
    def test_course_model_provides_none_values(self):
        """Test validates that a value of None is assigned to each property where that non-required, optional field is not provided
        
        Fields of default None value (unset on model creation) can be ignored and not inserted on document
        db inserts by using `collection.insert_one(model.model_dump(exclude_unset=True))`
        """
        course_id = "101"
        model = CourseBase(**{
            "course_id": course_id,
        })

        assert model.canvas_id == None
        assert model.milestones == None
        assert model.version == None
        assert model.course_id == course_id

    @pytest.mark.parametrize("data", [
        # Missing required field(s)
        {},
        
        # Extra field provided
        {"course_id": "101", "should not be here": "here"},

        # Incorrect type
        {"course_id": "101", "canvas_id": "z12345"},
    ])
    def test_course_model_invalid_cases(self, data):
        with pytest.raises(ValidationError):
            CourseBase(**data) # using Base model here rather than Model as not testing DB find result (pre-insert validation)

    @pytest.mark.integration
    def test_courses_schema_rejects_invalid_insert(self, real_mongo_db: pymongo.database.Database):
        """Integration test validating that a courses document will not be inserted
        if it does not follow the collection json validation schema.
        
        Relevant for inserts performed outside of API.
        """
        courses_collection = real_mongo_db.get_collection(COURSES_COLLECTION)

        with pytest.raises(pymongo.errors.WriteError, match="Document failed validation"):
            courses_collection.insert_one({
                "course_id": "101",
                "canvas_id": "12345", # if provided, needs to be integer value
                "title": "Introduction to Problem Solving",
                "milestones": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
                "version": "1.0.0"
            })

    @pytest.mark.integration
    def test_courses_schema_accepts_valid_insert(self, real_mongo_db: pymongo.database.Database):
        """Integration test validating that a courses document will be inserted
        if it follows the collection json validation schema.
        """
        courses_collection = real_mongo_db.get_collection(COURSES_COLLECTION)
        prev_count = courses_collection.count_documents({})

        course_id = "101"
        canvas_id = 12345
        title = "Introduction to Problem Solving"
        milestones = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        version = "1.0.0"

        # todo: upon a POST /api/courses endpoint creation, this direct insert can be replaced with a TestClient call
        insert_result = courses_collection.insert_one({
            "course_id": course_id,
            "canvas_id": canvas_id,
            "title": title,
            "milestones": milestones,
            "version": version
        })

        assert insert_result.acknowledged

        found_course = courses_collection.find_one({"_id": insert_result.inserted_id})
        assert found_course is not None
        assert found_course["course_id"] == course_id
        assert prev_count + 1 == courses_collection.count_documents({})


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
        
