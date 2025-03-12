import os
from unittest.mock import MagicMock
from mongomock import MongoClient as MockClient
from pymongo import MongoClient
import pytest
from sqlalchemy.orm import Session

from src.config import MONGO_DATABASE_NAME
from src.database.mongo.core import get_mongo
from src.database.mongo.service import init_collections
from src.database.postgres.core import make_session
from src.main import app

@pytest.fixture(scope="function")
def mock_mongo_db():
    """Injection for MongoDB dependency intended for fast, in-memory unit testing"""
    mock_client = MockClient()
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
    client = MongoClient(os.environ.get("CTI_MONGO_URL"))
    test_db_name = "test_" + MONGO_DATABASE_NAME
    db = client[test_db_name]
    init_collections(db, with_validators=True)

    app.dependency_overrides[get_mongo] = lambda: db

    yield db

    app.dependency_overrides.pop(get_mongo)
    client.drop_database(db)
    client.close()

@pytest.fixture(scope="function")
def mock_postgresql_db():
    """Fixture to mock a PostgreSQL database session for testing."""
    db = MagicMock(spec=Session)
    app.dependency_overrides[make_session] = lambda: db
    yield db
    app.dependency_overrides.pop(make_session)
