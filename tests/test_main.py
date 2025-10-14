from fastapi.testclient import TestClient
from src.config import settings
import pytest
from src.main import app

client = TestClient(app)

# Development environment tests

@pytest.mark.skipif(settings.app_env == "production", reason="Development only route")
def test_dev_root_message():
    """Verify root endpoint returns the expected message in development."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "cti-sys v1.0.0"}

@pytest.mark.skipif(settings.app_env == "production", reason="Development only route")
def test_dev_postgres_connection():
    """Confirm PostgreSQL connection test passes in development."""
    response = client.get("/test-connection")
    assert response.status_code == 200
    assert response.json() == {"message": "Database connection succeeded"}


# Production environment tests

@pytest.mark.skipif(settings.app_env != "production", reason="Production only route")
def test_prod_root_message():
    """Verify root endpoint returns the expected message in production."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "API running in production mode"}


@pytest.mark.skipif(settings.app_env != "production", reason="Production only route")
def test_prod_docs_disabled_message():
    """Ensure /docs returns a generic message in production."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert response.json() == {"message": "API documentation is not available in this environment."}