from fastapi.testclient import TestClient
from src.config import settings
import pytest
from src.main import app

client = TestClient(app)

@pytest.mark.skipif(settings.app_env == "production", reason="Health check route")
def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "cti-sys v1.0.0"}

@pytest.mark.skipif(settings.app_env == "production", reason="Health check route")
def test_confirm_conn():
    response = client.get("/test-connection")
    assert response.status_code == 200
    assert response.json() == {"message": "Database connection succeeded"}
