from datetime import datetime, timedelta
from unittest.mock import MagicMock
import pytz
from src.database.postgres.models import AccelerateCourseProgress
from src.students.accelerate.check_activity import service as svc

class TestCheckAccelerateActivity:  
      
    def test_student_active_with_both_attendance_and_canvas(self, client, monkeypatch, mock_postgresql_db):
        """Test student marked active when they have BOTH attendance and Canvas activity."""
        # Create a mock student who is very engaged
        student = MagicMock()
        student.cti_id = 1001
        student.fullname = "Super Active Student"
        student.active = True
        
        # Mock the database query to return our test student
        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.all.return_value = [student]
        mock_postgresql_db.query.return_value = mock_query
        
        # Create mock Accelerate record that starts as INACTIVE
        acc = MagicMock()
        acc.cti_id = 1001
        acc.active = False
        
        # Mock attendance check to return True - student HAS attended sessions
        monkeypatch.setattr(svc, "check_attendance", lambda db, cti_id, threshold: True)
        
        # Mock Canvas activity check to also return True with a recent login
        pacific_tz = pytz.timezone('America/Los_Angeles')
        last_login = datetime.now(pacific_tz).replace(tzinfo=None) - timedelta(hours=3)
        monkeypatch.setattr(svc, "check_canvas", lambda db, cti_id, threshold: (True, last_login))
        
        def mock_filter_side_effect(*args, **kwargs):
            mock_result = MagicMock()
            mock_result.first.return_value = acc
            return mock_result
        
        # Set up database operation mocks
        mock_postgresql_db.query.return_value.filter.side_effect = mock_filter_side_effect
        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.add.return_value = None
        
        # Make the API call
        res = client.post("/api/students/accelerate/check-activity")
        
        # Verify the response
        assert res.status_code == 200
        data = res.json()
        assert data["students_marked_active"] == 1
        assert data["students_marked_inactive"] == 0
        
        # Verify BOTH activity types are tracked in the response
        assert data["details"][0]["attendance_activity"] == True
        assert data["details"][0]["canvas_activity"] == True
        assert data["details"][0]["last_canvas_access"] is not None
        assert data["details"][0]["active"] == True
        
        # Verify the status changed to active in the database
        assert acc.active == True
    
    
    def test_student_active_with_attendance_only(self, client, monkeypatch, mock_postgresql_db):
        """Test student marked active due to attendance only (no Canvas activity)."""
        # Create a mock student
        student = MagicMock()
        student.cti_id = 2001
        student.fullname = "Attendance Only Student"
        student.active = True
        
        # Mock the database query
        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.all.return_value = [student]
        mock_postgresql_db.query.return_value = mock_query
        
        # Create mock Accelerate record starting as INACTIVE
        acc = MagicMock()
        acc.cti_id = 2001
        acc.active = False
        
        # Mock attendance check to return True - student HAS attended sessions
        monkeypatch.setattr(svc, "check_attendance", lambda db, cti_id, threshold: True)
        
        # Mock Canvas check to return False - NO Canvas activity
        monkeypatch.setattr(svc, "check_canvas", lambda db, cti_id, threshold: (False, None))
        
        def mock_filter_side_effect(*args, **kwargs):
            mock_result = MagicMock()
            mock_result.first.return_value = acc
            return mock_result
        
        mock_postgresql_db.query.return_value.filter.side_effect = mock_filter_side_effect
        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.add.return_value = None
        
        # Make the API call
        res = client.post("/api/students/accelerate/check-activity")
        
        # Verify the response
        assert res.status_code == 200
        data = res.json()
        assert data["students_marked_active"] == 1
        
        # Verify only attendance activity is true
        assert data["details"][0]["attendance_activity"] == True
        assert data["details"][0]["canvas_activity"] == False
        assert data["details"][0]["last_canvas_access"] is None
        assert data["details"][0]["active"] == True
        
        # Verify status changed to active
        assert acc.active == True
    
    
    def test_student_active_with_canvas_only(self, client, monkeypatch, mock_postgresql_db):
        """Test student marked active due to Canvas activity only (no attendance)."""
        # Create a mock student
        student = MagicMock()
        student.cti_id = 3001
        student.fullname = "Canvas Only Student"
        student.active = True
        
        # Mock the database query
        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.all.return_value = [student]
        mock_postgresql_db.query.return_value = mock_query
        
        # Create mock Accelerate record starting as INACTIVE
        acc = MagicMock()
        acc.cti_id = 3001
        acc.active = False
        
        # Mock attendance check to return False - NO attendance
        monkeypatch.setattr(svc, "check_attendance", lambda db, cti_id, threshold: False)
        
        # Mock Canvas check to return True with recent login
        pacific_tz = pytz.timezone('America/Los_Angeles')
        last_login = datetime.now(pacific_tz).replace(tzinfo=None) - timedelta(hours=6)
        monkeypatch.setattr(svc, "check_canvas", lambda db, cti_id, threshold: (True, last_login))
        
        def mock_filter_side_effect(*args, **kwargs):
            mock_result = MagicMock()
            mock_result.first.return_value = acc
            return mock_result
        
        mock_postgresql_db.query.return_value.filter.side_effect = mock_filter_side_effect
        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.add.return_value = None
        
        # Make the API call
        res = client.post("/api/students/accelerate/check-activity")
        
        # Verify the response
        assert res.status_code == 200
        data = res.json()
        assert data["students_marked_active"] == 1
        assert data["students_marked_inactive"] == 0
        
        # Verify only Canvas activity is true
        assert data["details"][0]["attendance_activity"] == False
        assert data["details"][0]["canvas_activity"] == True
        assert data["details"][0]["last_canvas_access"] is not None
        assert data["details"][0]["active"] == True
        
        # Verify status changed to active
        assert acc.active == True
    
    
    def test_student_inactive_with_no_activity(self, client, monkeypatch, mock_postgresql_db):
        """Test student marked inactive when they have NO attendance or Canvas activity."""
        # Create a mock student
        student = MagicMock()
        student.cti_id = 4001
        student.fullname = "Inactive Student"
        student.active = True
        
        # Mock the database query
        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.all.return_value = [student]
        mock_postgresql_db.query.return_value = mock_query
        
        # Create mock Accelerate record starting as ACTIVE (will change to inactive)
        acc = MagicMock()
        acc.cti_id = 4001
        acc.active = True
        
        # Mock attendance check to return False - NO attendance
        monkeypatch.setattr(svc, "check_attendance", lambda db, cti_id, threshold: False)
        
        # Mock Canvas check to return False - NO Canvas activity
        monkeypatch.setattr(svc, "check_canvas", lambda db, cti_id, threshold: (False, None))
        
        def mock_filter_side_effect(*args, **kwargs):
            mock_result = MagicMock()
            mock_result.first.return_value = acc
            return mock_result
        
        mock_postgresql_db.query.return_value.filter.side_effect = mock_filter_side_effect
        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.add.return_value = None
        
        # Make the API call
        res = client.post("/api/students/accelerate/check-activity")
        
        # Verify the response
        assert res.status_code == 200
        data = res.json()
        assert data["students_marked_active"] == 0
        assert data["students_marked_inactive"] == 1
        
        # Verify no activity detected
        assert data["details"][0]["attendance_activity"] == False
        assert data["details"][0]["canvas_activity"] == False
        assert data["details"][0]["last_canvas_access"] is None
        assert data["details"][0]["active"] == False
        
        # Verify status changed to inactive
        assert acc.active == False
    
    
    def test_no_active_students(self, client, mock_postgresql_db):
        """Test case where no active students are found."""
        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.all.return_value = []
        mock_postgresql_db.query.return_value = mock_query
        mock_postgresql_db.commit.return_value = None
        
        res = client.post("/api/students/accelerate/check-activity")
        
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == 200
        assert data["students_processed"] == 0
        assert data["students_marked_active"] == 0
        assert data["students_marked_inactive"] == 0
        assert len(data["details"]) == 0
        assert len(data["errors"]) == 0
    
    
    def test_canvas_api_error_handled_gracefully(self, client, monkeypatch, mock_postgresql_db):
        """Test that Canvas API errors are handled per-student without crashing."""
        student_1 = MagicMock()
        student_1.cti_id = 3001
        student_1.fullname = "Error Student"
        student_1.active = True
        
        student_2 = MagicMock()
        student_2.cti_id = 3002
        student_2.fullname = "Good Student"
        student_2.active = True
        
        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.all.return_value = [student_1, student_2]
        mock_postgresql_db.query.return_value = mock_query
        
        acc_1 = MagicMock()
        acc_1.cti_id = 3001
        acc_1.active = True
        
        acc_2 = MagicMock()
        acc_2.cti_id = 3002
        acc_2.active = False
        
        monkeypatch.setattr(svc, "check_attendance", lambda db, cti_id, threshold: True)
        
        def mock_check_canvas(db, cti_id, threshold):
            if cti_id == 3001:
                raise ValueError("Canvas API authentication failed")
            return False, None
        
        monkeypatch.setattr(svc, "check_canvas", mock_check_canvas)
        
        def mock_filter_side_effect(*args, **kwargs):
            mock_result = MagicMock()
            filter_expr = args[0] if args else None
            if hasattr(filter_expr, 'left') and hasattr(filter_expr.left, 'name'):
                if filter_expr.left.name == 'cti_id':
                    cti_id = filter_expr.right.value
                    mock_result.first.return_value = acc_1 if cti_id == 3001 else acc_2
            return mock_result
        
        mock_postgresql_db.query.return_value.filter.side_effect = mock_filter_side_effect
        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.rollback.return_value = None
        mock_postgresql_db.add.return_value = None
        
        res = client.post("/api/students/accelerate/check-activity")
        
        assert res.status_code == 200
        data = res.json()
        assert data["students_processed"] == 2
        assert len(data["errors"]) == 1
        assert data["errors"][0]["cti_id"] == 3001
        assert "Canvas API" in data["errors"][0]["error"]
        assert mock_postgresql_db.rollback.call_count == 1
        assert mock_postgresql_db.commit.call_count == 1
    
    
    def test_creates_accelerate_course_progress_record(self, client, monkeypatch, mock_postgresql_db):
        """Test that accelerate_course_progress records are created if they don't exist."""
        student = MagicMock()
        student.cti_id = 5001
        student.fullname = "New Progress"
        student.active = True
        
        acc = MagicMock()
        acc.cti_id = 5001
        acc.active = False
        
        monkeypatch.setattr(svc, "check_attendance", lambda db, cti_id, threshold: True)
        
        pacific_tz = pytz.timezone('America/Los_Angeles')
        last_login = datetime.now(pacific_tz).replace(tzinfo=None)
        monkeypatch.setattr(svc, "check_canvas", lambda db, cti_id, threshold: (True, last_login))
        
        added_records = []
        
        def mock_add(record):
            added_records.append(record)
        
        def mock_query_side_effect(model):
            mock_result = MagicMock()
            mock_result.join.return_value.filter.return_value.all.return_value = [student]
            mock_result.filter.return_value.first.return_value = acc if model.__name__ == 'Accelerate' else None
            return mock_result
        
        mock_postgresql_db.query.side_effect = mock_query_side_effect
        mock_postgresql_db.add.side_effect = mock_add
        mock_postgresql_db.commit.return_value = None
        
        res = client.post("/api/students/accelerate/check-activity")
        
        assert res.status_code == 200
        assert len(added_records) == 1
        assert isinstance(added_records[0], AccelerateCourseProgress)
        assert added_records[0].cti_id == 5001
        assert added_records[0].last_canvas_access == last_login


    def test_updates_existing_accelerate_course_progress_record(self, client, monkeypatch, mock_postgresql_db):
        """Test that existing accelerate_course_progress records are updated with new last_canvas_access."""
        student = MagicMock()
        student.cti_id = 6001
        student.fullname = "Existing Progress"
        student.active = True
        
        acc = MagicMock()
        acc.cti_id = 6001
        acc.active = False
        
        pacific_tz = pytz.timezone('America/Los_Angeles')
        old_login = datetime.now(pacific_tz).replace(tzinfo=None) - timedelta(days=10)
        existing_progress = MagicMock()
        existing_progress.cti_id = 6001
        existing_progress.last_canvas_access = old_login
        
        monkeypatch.setattr(svc, "check_attendance", lambda db, cti_id, threshold: True)
        
        new_login = datetime.now(pacific_tz).replace(tzinfo=None) - timedelta(hours=2)
        monkeypatch.setattr(svc, "check_canvas", lambda db, cti_id, threshold: (True, new_login))
        
        added_records = []
        
        def mock_add(record):
            added_records.append(record)
        
        def mock_query_side_effect(model):
            mock_result = MagicMock()
            mock_result.join.return_value.filter.return_value.all.return_value = [student]
            if model.__name__ == 'Accelerate':
                mock_result.filter.return_value.first.return_value = acc
            elif model.__name__ == 'AccelerateCourseProgress':
                mock_result.filter.return_value.first.return_value = existing_progress
            else:
                mock_result.filter.return_value.first.return_value = None
            return mock_result
        
        mock_postgresql_db.query.side_effect = mock_query_side_effect
        mock_postgresql_db.add.side_effect = mock_add
        mock_postgresql_db.commit.return_value = None
        
        res = client.post("/api/students/accelerate/check-activity")
        
        assert res.status_code == 200
        assert len([r for r in added_records if isinstance(r, AccelerateCourseProgress)]) == 0
        assert existing_progress.last_canvas_access == new_login
        assert existing_progress.last_canvas_access != old_login


    def test_no_canvas_id_skips_canvas_check(self, client, monkeypatch, mock_postgresql_db):
        """Test that students without a canvas_id record don't get Canvas activity checked."""
        student = MagicMock()
        student.cti_id = 7001
        student.fullname = "No Canvas"
        student.active = True
        
        acc = MagicMock()
        acc.cti_id = 7001
        acc.active = True
        
        monkeypatch.setattr(svc, "check_attendance", lambda db, cti_id, threshold: True)
        
        def mock_query_side_effect(model):
            mock_result = MagicMock()
            mock_result.join.return_value.filter.return_value.all.return_value = [student]
            if model.__name__ == 'CanvasID':
                mock_result.filter.return_value.first.return_value = None
            elif model.__name__ == 'Accelerate':
                mock_result.filter.return_value.first.return_value = acc
            else:
                mock_result.filter.return_value.first.return_value = None
            return mock_result
        
        mock_postgresql_db.query.side_effect = mock_query_side_effect
        mock_postgresql_db.commit.return_value = None
        mock_postgresql_db.add.return_value = None
        
        res = client.post("/api/students/accelerate/check-activity")
        
        assert res.status_code == 200
        data = res.json()
        assert data["students_marked_active"] == 1
        assert data["details"][0]["canvas_activity"] == False
        assert data["details"][0]["last_canvas_access"] is None
        assert acc.active == True


