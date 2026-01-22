import requests
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_
import pytz

from src.database.postgres.models import StudentEmail
from src.config import settings
from src.database.postgres.models import (
    Student, Accelerate, AccelerateCourseProgress, 
    CanvasID, StudentAttendance, Attendance
)


def get_current_pacific_time() -> datetime:
    """Get current time in Pacific timezone as naive datetime."""
    pacific_time_zone = pytz.timezone('America/Los_Angeles')
    return datetime.now(pacific_time_zone).replace(tzinfo=None)


def fetch_canvas_last_login(canvas_id: int) -> Optional[datetime]:
    """Fetch last_login timestamp from Canvas API and convert to Pacific time."""
    if not settings.cti_access_token:
        raise ValueError("Missing Canvas API configuration (CTI_ACCESS_TOKEN)")
    
    url = f"{settings.canvas_api_test_url}/api/v1/users/{canvas_id}"
    
    response = requests.get(
        url,
        params={"include[]": "last_login"},
        headers={"Authorization": f"Bearer {settings.cti_access_token}"},
        timeout=10,
    )
    
    if response.status_code == 404:
        return None
    
    if response.status_code == 401:
        raise ValueError(
            "Please check that CTI_ACCESS_TOKEN is set correctly and has not expired."
        )
        
    response.raise_for_status()
    user_data = response.json()
    
    last_login_raw = user_data.get("last_login")
    if not last_login_raw:
        return None
    
    # Parse UTC datetime from Canvas and convert to Pacific time
    last_login_utc = datetime.fromisoformat(last_login_raw.replace("Z", "+00:00"))
    pacific_time_zone = pytz.timezone('America/Los_Angeles')
    last_login_pacific = last_login_utc.astimezone(pacific_time_zone)
    
    return last_login_pacific.replace(tzinfo=None)


def check_attendance(db: Session, cti_id: int, threshold_weeks: int) -> bool:
    """Check if a student has attended any Accelerate session within the threshold period."""
    now = get_current_pacific_time()
    check_start_date = now - timedelta(days=threshold_weeks * 7)
    
    attendance_exists = db.query(StudentAttendance).join(
        Attendance, StudentAttendance.session_id == Attendance.session_id
    ).filter(
        and_(
            StudentAttendance.cti_id == cti_id,
            Attendance.program == "Accelerate",
            Attendance.session_start >= check_start_date
        )
    ).first()
    
    return attendance_exists is not None


def check_canvas(db: Session, cti_id: int, threshold_weeks: int) -> Tuple[bool, Optional[datetime]]:
    """Check if a student has accessed Canvas within the threshold period."""
    canvas_record = db.query(CanvasID).filter(CanvasID.cti_id == cti_id).first()
    if not canvas_record:
        return False, None
    
    last_login = fetch_canvas_last_login(canvas_record.canvas_id)
    if not last_login:
        return False, None
    
    now = get_current_pacific_time()
    check_start_date = now - timedelta(days=threshold_weeks * 7)
    is_active = last_login >= check_start_date
    
    return is_active, last_login


def update_activity_status(
    db: Session,
    cti_id: int,
    is_active: bool,
    last_canvas_access: Optional[datetime]
) -> bool:
    """Update the accelerate.active status and accelerate_course_progress record."""
    accelerate_record = db.query(Accelerate).filter(Accelerate.cti_id == cti_id).first()
    if not accelerate_record:
        return False
    
    accelerate_record.active = is_active
    
    # Update or create progress record if we have Canvas access data
    if last_canvas_access:
        progress_record = db.query(AccelerateCourseProgress).filter(
            AccelerateCourseProgress.cti_id == cti_id
        ).first()

        if progress_record:
            progress_record.last_canvas_access = last_canvas_access
        else:
            progress_record = AccelerateCourseProgress(
                cti_id=cti_id,
                last_canvas_access=last_canvas_access
            )
            db.add(progress_record)
    
    return True


def process_student_activity(
    db: Session,
    student: Student,
    att_threshold: int,
    canvas_threshold: int
) -> Dict[str, Any]:
    """Process a single student's activity check."""
    cti_id = student.cti_id
    
    # Check both activity types
    has_attendance_activity = check_attendance(db, cti_id, att_threshold)
    has_canvas_activity, last_canvas_access = check_canvas(db, cti_id, canvas_threshold)
    
    # Student is active if they have either type of activity
    is_active = has_attendance_activity or has_canvas_activity
    
    if not update_activity_status(db, cti_id, is_active, last_canvas_access):
        return {
            "cti_id": cti_id,
            "error": "No Accelerate record found for this student"
        }
    
    # Get student email
    email_record = db.query(StudentEmail).filter(StudentEmail.cti_id == cti_id).first()
    cti_email = email_record.email if email_record else None
    
    # Format last canvas access for JSON response
    last_canvas_str = last_canvas_access.isoformat() if last_canvas_access else None
    
    return {
        "cti_id": cti_id,
        "email": cti_email,
        "name": student.fullname,
        "attendance_activity": has_attendance_activity,
        "canvas_activity": has_canvas_activity,
        "last_canvas_access": last_canvas_str,
        "active": is_active,
    }


def check_all_students(
    db: Session,
    att_threshold: int,
    canvas_threshold: int
) -> Dict[str, Any]:
    """
    Check and update activity status for all active Accelerate students.
    Commits changes per student to avoid long transactions.
    """
    active_students = db.query(Student).join(
        Accelerate, Student.cti_id == Accelerate.cti_id
    ).filter(
        Student.active == True
    ).all()
    
    results = {
        "status": 200,
        "students_processed": len(active_students),
        "students_marked_active": 0,
        "students_marked_inactive": 0,
        "details": [],
        "errors": [],
    }
    
    for student in active_students:
        try:
            result = process_student_activity(db, student, att_threshold, canvas_threshold)
            
            if "error" in result:
                results["errors"].append(result)
                db.rollback()
            else:
                db.commit()
                
                if result["active"]:
                    results["students_marked_active"] += 1
                else:
                    results["students_marked_inactive"] += 1
                
                results["details"].append(result)
                
        except Exception as e:
            db.rollback()
            results["errors"].append({"cti_id": student.cti_id, "error": str(e)})
    
    return results