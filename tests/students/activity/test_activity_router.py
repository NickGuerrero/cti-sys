from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from unittest.mock import MagicMock

from src.main import app
from src.database.postgres.models import Student


client = TestClient(app)

class TestCheckActivity:
    def test_check_activity_active(self, mock_postgresql_db):
        """Test checking activity for active students based only on attendance."""
        mock_db = mock_postgresql_db
        mock_student_active = Student(cti_id=1, fname="John", lname="Doe", active=True)

        # Mock the Student query result
        mock_db.query.return_value.filter.return_value.all.side_effect = [
            [mock_student_active]
        ]
        # Mock attendance count
        mock_db.query.return_value.join.return_value.filter.return_value.count.return_value = 1

        request_data = {
            "target": "active",
            "active_start": (datetime.now() - timedelta(weeks=2)).isoformat(),
            "activity_thresholds": {
                "last_attended_session": ["2024-07-04"]
            }
        }

        response = client.post("/api/students/activity/check-activity?program=accelerate", json=request_data)
        assert response.status_code == 200
        assert response.json() == {"status": 200}
        mock_db.commit.assert_called_once()

    def test_check_activity_inactive(self, mock_postgresql_db):
        """Test checking activity for inactive students."""
        mock_db = mock_postgresql_db
        mock_student_inactive = Student(cti_id=2, fname="Jane", lname="Doe", active=False)

        mock_db.query.return_value.filter.return_value.all.side_effect = [
            [mock_student_inactive]
        ]
        mock_db.query.return_value.join.return_value.filter.return_value.count.return_value = 0

        request_data = {
            "target": "inactive",
            "active_start": (datetime.now() - timedelta(weeks=2)).isoformat(),
            "activity_thresholds": {
                "last_attended_session": ["2024-07-04"]
            }
        }

        response = client.post("/api/students/activity/check-activity?program=accelerate", json=request_data)
        assert response.status_code == 200
        assert response.json() == {"status": 200}
        mock_db.commit.assert_called_once()

    def test_check_activity_both(self, mock_postgresql_db):
        """Test checking activity for both active and inactive students."""
        mock_db = mock_postgresql_db
        mock_student_active = Student(cti_id=1, fname="John", lname="Doe", active=True)
        mock_student_inactive = Student(cti_id=2, fname="Jane", lname="Doe", active=False)

        mock_db.query.return_value.filter.return_value.all.side_effect = [
            [mock_student_active, mock_student_inactive]
        ]
        # Return count=1, meaning at least one attendance record
        mock_db.query.return_value.join.return_value.filter.return_value.count.return_value = 1

        request_data = {
            "target": "both",
            "active_start": (datetime.now() - timedelta(weeks=2)).isoformat(),
            "activity_thresholds": {
                "last_attended_session": ["2024-07-04"]
            }
        }

        response = client.post("/api/students/activity/check-activity?program=accelerate", json=request_data)
        assert response.status_code == 200
        assert response.json() == {"status": 200}
        mock_db.commit.assert_called_once()

    def test_database_error_handling(self, mock_postgresql_db):
        """Test handling of SQLAlchemy database errors."""
        mock_db = mock_postgresql_db
        mock_student_active = Student(cti_id=1, fname="John", lname="Doe", active=True)

        mock_db.query.return_value.filter.return_value.all.side_effect = [
            [mock_student_active]
        ]

        mock_db.commit.side_effect = SQLAlchemyError("Database error")

        request_data = {
            "target": "both",
            "active_start": (datetime.now() - timedelta(weeks=2)).isoformat(),
            "activity_thresholds": {
                "last_attended_session": ["2024-07-04"]
            }
        }

        response = client.post("/api/students/activity/check-activity?program=accelerate", json=request_data)

        assert response.status_code == 500
        assert "Database error" in response.json()["detail"]
        assert mock_db.rollback.called