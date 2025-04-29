from fastapi.testclient import TestClient

from src.main import app
from datetime import date, timedelta

from src.database.postgres.models import Accelerate
from src.students.accelerate.process_attendance import service as svc

client = TestClient(app)

class TestProcessAccelerateAttendance:
    def test_process_attendance_success(self, monkeypatch, mock_postgresql_db):
        """
        Simulate a case where two active students are returned from the database.
            - Two active Accelerate rows are returned, metrics are written, and the transaction is committed.
            - The route returns {status: 200, records_updated: 2}.
            - The database is modified.
            - The attendance rows are not empty.
        """
        acc_1 = Accelerate(cti_id=1, active=True)
        acc_2 = Accelerate(cti_id=2, active=True)

        monkeypatch.setattr(svc, "load_active_accelerate_records", lambda db: [acc_1, acc_2])
        fake_rows = [
            (1, date(2025, 4, 1), 1.0),
            (2, date(2025, 4, 1), 0.5),
        ]
        monkeypatch.setattr(svc, "load_attendance_rows", lambda db, ids: fake_rows)

        canned = {
            1: dict(participation_score=1.0, sessions_attended=1, participation_streak=1, inactive_weeks=0),
            2: dict(participation_score=0.5, sessions_attended=1, participation_streak=1, inactive_weeks=0),
        }

        def fake_metrics(weekly, **_):
            first_score = next(iter(weekly.values()))[0]
            return canned[1] if first_score == 1.0 else canned[2]

        monkeypatch.setattr(svc, "metrics_for_student", fake_metrics)

        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.rollback.return_value = None

        res = client.post("/api/students/accelerate/process-attendance")
        assert res.status_code == 200
        assert res.json() == {"status": 200, "records_updated": 2}
        mock_postgresql_db.commit.assert_called_once()
        mock_postgresql_db.rollback.assert_not_called()
        assert acc_1.participation_score == 1.0
        assert acc_2.participation_score == 0.5


    def test_no_active_students(self, monkeypatch, mock_postgresql_db):
        """
        Simulate a case where no active students are returned from the database.
            - Two active Accelerate rows are returned, metrics are written,
            - One commit occurs, and the route returns {status: 200, records_updated: 0}.
            - The database is not modified.
            - The attendance rows are empty.
        """
        monkeypatch.setattr(svc, "load_active_accelerate_records", lambda db: [])
        monkeypatch.setattr(svc, "load_attendance_rows", lambda db, ids: [])

        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.rollback.return_value = None

        res = client.post("/api/students/accelerate/process-attendance")
        assert res.status_code == 200
        assert res.json() == {"status": 200, "records_updated": 0}
        mock_postgresql_db.commit.assert_called_once()
        mock_postgresql_db.rollback.assert_not_called()


    def test_database_error_triggers_rollback(self, monkeypatch, mock_postgresql_db):
        """
        Simulate a database error during the transaction.
            - return HTTP-500
            - call rollback once
            - never call commit
        """
        monkeypatch.setattr(
            svc,
            "load_active_accelerate_records",
            lambda db: (_ for _ in ()).throw(RuntimeError("DB failure")),
        )

        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.rollback.return_value = None

        # Turn server exceptions into HTTP-500 responses.
        safe_client = TestClient(app, raise_server_exceptions=False)
        res = safe_client.post("api/students/accelerate/process-attendance")

        assert res.status_code == 500
        mock_postgresql_db.rollback.assert_called_once()
        mock_postgresql_db.commit.assert_not_called()


    def test_weighted_vs_plain_average(self):
        """
        Weekly averages: 1.0 (newest), 1.0, 0.5, 0.25 (oldest)
        
        Using plain mean: 
            - (1.0 + 1.0 + 0.5 + 0.25) / 4 = 0.6875

        Using weighted mean with decay 0.90:
            - The most recent week (w0) is weighted 0.9, the next week (w1) is weighted 0.81, etc.
            - The weights are: 0.9, 0.81, 0.729, 0.6561
            - The weighted average is: (1.0 * 0.9 + 1.0 * 0.81 + 0.5 * 0.729 + 0.25 * 0.6561) / (0.9 + 0.81 + 0.729 + 0.6561)
            - The denominator is the sum of the weights: 0.9 + 0.81 + 0.729 + 0.6561 = 3.0961
            - = (0.9 + 0.81 + 0.3645 + 0.164025) / (3.0961) = 0.72
            
        Using weighted mean with decay 0.75:
            - The most recent week (w0) is weighted 0.75, the next week (w1) is weighted 0.5625, etc.
            - The weights are: 0.75, 0.5625, 0.421875, 0.31640625
            - The weighted average is: (1.0 * 0.75 + 1.0 * 0.5625 + 0.5 * 0.421875 + 0.25 * 0.31640625) / (0.75 + 0.5625 + 0.421875 + 0.31640625)
            - The denominator is the sum of the weights: 0.75 + 0.5625 + 0.421875 + 0.31640625 = 2.05078125  
            - = (0.75 + 0.5625 + 0.2109375 + 0.0791015625) / (2.05078125) = 0.78
            
        
        Summary:
            - The plain mean is less sensitive to recent changes in participation.
            - The weighted average is more sensitive to recent changes in participation.
            - The weighted average is higher than the plain mean because the most recent weeks are given more weight.

        The expected results are:
            - Plain mean: 0.69
            - Weighted (decay = 0.90): 0.72
            - Weighted (decay = 0.75): 0.78
        """
        today = date(2025, 4, 28)
        w0 = today - timedelta(days=today.weekday())
        w1 = w0 - timedelta(weeks=1)
        w2 = w0 - timedelta(weeks=2)
        w3 = w0 - timedelta(weeks=3)

        data = [(w0, 1.0), (w1, 1.0), (w2, 0.5), (w3, 0.25)]

        # Using plain mean
        plain = svc.weighted_participation_score(data, weighted=False)
        assert round(plain, 2) == 0.69

        # Weighted=True and decay=0.90
        weighted = svc.weighted_participation_score(data, weighted=True, decay=0.90)
        assert round(weighted, 2) == 0.72

        # Weighted=True and decay=0.75
        weighted_low_decay = svc.weighted_participation_score(data, weighted=True, decay=0.75)
        assert round(weighted_low_decay, 2) == 0.78
        

    def test_metrics_for_student_full_set(self):
        """
        Two sessions this week (average 1.0) and one last week (0.5).
            - participation_score: 0.75
            - sessions_attended : 3
            - participation_streak: 2
            - inactive_weeks: 0
        """
        today = date(2025, 4, 28)
        w0 = today - timedelta(days=today.weekday())
        w1 = w0 - timedelta(weeks=1)

        rows = [(w0, 1.0), (w0, 1.0), (w1, 0.5)]

        weekly = svc.compute_weekly_aggregates(rows)
        m = svc.metrics_for_student(weekly)

        assert round(m["participation_score"], 3) == 0.75
        assert m["sessions_attended"] == 3
        assert m["participation_streak"] == 2
        assert m["inactive_weeks"] == 0