from unittest.mock import MagicMock
from mongomock import MongoClient as MockClient
from pymongo import MongoClient
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from src.config import MONGO_DATABASE_NAME, settings
from src.database.mongo.core import get_mongo
from src.database.mongo.service import init_collections
from src.database.postgres.core import make_session
from src.main import app
import gspread

@pytest.fixture(scope="function")
def mock_gspread(monkeypatch):
    """
    Fixture to mock gspread authentication.
    This overrides both production and development credential paths.
    """
    mock_gc = MagicMock(spec=gspread.Client)
    
    # Mock the production path
    monkeypatch.setattr("src.gsheet.utils.create_credentials", lambda: mock_gc)
    # Mock the development path
    monkeypatch.setattr("gspread.service_account", lambda filename: mock_gc)
    
    return mock_gc

# Fixtures for tests
@pytest.fixture(scope="session", autouse=True)
def override_cti_admin_key():
    """Ensure tests always use a fixed admin API key"""
    settings.cti_sys_admin_key = "TEST_KEY"

@pytest.fixture(scope="session")
def auth_headers():
    """Reusable Authorization header for API requests"""
    return {"Authorization": "Bearer TEST_KEY"}

@pytest.fixture(scope="session")
def client(auth_headers):
    """Shared FastAPI test client with auth headers included"""
    client = TestClient(app)
    client.headers.update(auth_headers)
    return client

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
    client = MongoClient(settings.cti_mongo_url)
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

@pytest.fixture(scope="session", autouse=True)
def global_canvas_api_url_override():
    """Fixture to override the Canvas URL in favor of the test environment"""
    canvas_api_url = settings.canvas_api_url
    settings.canvas_api_url = settings.canvas_api_test_url
    yield
    settings.canvas_api_url = canvas_api_url
    