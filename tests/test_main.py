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
from src.app.models.mongo.models import ApplicationModel, DeepWork
from src.app.models.mongo.schemas import init_collections
from src.config import ACCELERATE_FLEX_COLLECTION, APPLICATIONS_COLLECTION, MONGO_DATABASE_NAME, PATHWAY_GOALS_COLLECTION
from src.db_scripts.mongo import get_mongo
from src.main import app

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

        found_pathway_goals = pathway_goals_collection.find_one({"_id": insert_result.inserted_id})
        assert found_pathway_goals is not None
        assert found_pathway_goals["pathway_goal"] == pathway_goal
        assert prev_count + 1 == pathway_goals_collection.count_documents({})
