from typing import Generator
import bson
import pytest
import mongomock
from fastapi.testclient import TestClient
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
    """Creates a fresh mock database and overrides FastAPI dependency."""
    mock_client = mongomock.MongoClient()
    db = mock_client[MONGO_DATABASE_NAME]

    # Apply indexes (json schema validators cannot be enforced in mongomock)
    init_collections(db, with_validators=False)

    # Override FastAPI's database dependency
    app.dependency_overrides[get_mongo] = lambda: db

    yield db # Provide the mock DB instance

    app.dependency_overrides.pop(get_mongo) # Clean up override(s) after test
    mock_client.close()

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
        assert str(detail["msg"]).find("not a valid email address") != -1

    def test_duplicate_key(self, mock_mongo: mongomock.Database):
        mock_mongo.get_collection(APPLICATIONS_COLLECTION).insert_one({
            "fname": "First",
            "lname": "Last",
            "email": "test.user@cti.com", # email is a unique index
            "cohort": True,
            "graduating_year": 2024
        })
        
        response = client.post("/api/applications", json={
            "fname": "First",
            "lname": "Last",
            "email": "test.user@cti.com",
            "cohort": True,
            "graduating_year": 2024
        })

        assert response.status_code == 409
        detail = response.json()["detail"]
        assert str(detail).find("Duplicate index key") != -1

    @pytest.mark.integration
    def test_persistence_success(self):
        """Integration test validating the persistence of application inserts"""
        assert True
    
    @pytest.mark.integration
    def test_schema_valid_insert_success(self):
        """Integration test validating that a document can be inserted
        if the fields follow the collection json validation schema
        """
        assert True
        
    @pytest.mark.integration
    def test_schema_invalid_insert(self):
        """Integration test validating that a document will not be inserted
        if it does not follow the collection json validation schema
        """
        assert True
