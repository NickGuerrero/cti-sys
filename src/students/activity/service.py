from datetime import datetime
from typing import Dict, List

from sqlalchemy.orm import Session
from src.database.postgres.models import Student, Attendance, StudentAttendance

def check_student_activity(
    student: Student,
    active_start: datetime,
    activity_thresholds: Dict[str, List[str]],
    db: Session
) -> bool:
    """Check if a student is active based on attendance."""
    attended_sessions = db.query(StudentAttendance).join(Attendance).filter(
        StudentAttendance.cti_id == student.cti_id,
        Attendance.session_start >= active_start,
        Attendance.session_type.in_(activity_thresholds.get("last_attended_session", []))
    ).count()

    return attended_sessions > 0

def process_student_activity(
    request,
    program: str,
    db: Session
):
    """Process student activity based on the request."""
    if request.target == "active":
        students = db.query(Student).filter(Student.active.is_(True)).all()
    elif request.target == "inactive":
        students = db.query(Student).filter(Student.active.is_(False)).all()
    elif request.target == "both":
        students = db.query(Student).all()
    else:
        raise ValueError("Invalid target")

    for student in students:
        is_active = check_student_activity(student, request.active_start, request.activity_thresholds, db)
        student.active = is_active

    db.commit()