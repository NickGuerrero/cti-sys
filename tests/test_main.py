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
def mock_mongo():
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
def test_mongo():
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
    def test_min_required_success(self, mock_mongo: mongomock.Database):
        response = client.post("/api/applications", json={
            "fname": "First",
            "lname": "Last",
            "email": "test.user@cti.com"
        })

        assert response.status_code == 201
        assert bson.ObjectId.is_valid(response.json()["_id"])

    def test_extras_success(self, mock_mongo: mongomock.Database):
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

    def test_missing_required_field(self, mock_mongo: mongomock.Database):
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

    def test_invalid_email(self, mock_mongo: mongomock.Database):
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

    def test_duplicate_key(self, mock_mongo: mongomock.Database):
        app = ApplicationModel(
            fname="First",
            lname="Last",
            email="test.user@cti.com", # email is a unique index
            cohort=True,
            graduating_year=2024,
            app_submitted=datetime.now(timezone.utc)
        )
        
        mock_mongo.get_collection(APPLICATIONS_COLLECTION).insert_one(app.model_dump())
        
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
    def test_persistence_success(self, test_mongo: pymongo.database.Database):
        """Integration test validating that a document can be inserted and found
        if the fields follow the collection schema
        """
        app_collection = test_mongo.get_collection(APPLICATIONS_COLLECTION)

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
    def test_schema_rejects_invalid_insert(self, test_mongo: pymongo.database.Database):
        """Integration test validating that a document will not be inserted
        if it does not follow the collection json validation schema.
        
        Relevant for inserts performed outside of API.
        """
        app_collection = test_mongo.get_collection(APPLICATIONS_COLLECTION)

        with pytest.raises(pymongo.errors.WriteError, match="Document failed validation"):
            app_collection.insert_one({
                "fname": "First",
                "lname": "Last",
                "email": "test.user@cti.com"
                # missing app_submitted
            })
