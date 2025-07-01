from datetime import datetime
from typing import Dict, List
from sqlalchemy.orm import Session
from src.database.postgres.models import Student, Attendance, StudentAttendance, Accelerate

def process_student_activity(request, program: str, db: Session):
    if program == "accelerate":
        if request.target == "active":
            students = db.query(Student).filter(Student.active.is_(True)).all()
        elif request.target == "inactive":
            students = db.query(Student).filter(Student.active.is_(False)).all()
        elif request.target == "both":
            students = db.query(Student).all()
        else:
            raise ValueError("Invalid target")

        for idx, student in enumerate(students, start=1):
            is_active = _check_attendance_threshold(
                student.cti_id, request.active_start, request.activity_thresholds, db
            )
            student.active = is_active

            acc_record = db.query(Accelerate).filter(Accelerate.cti_id == student.cti_id).first()
            if acc_record:
                acc_record.active = is_active

    else:
        # Overall or other program
        if request.target == "active":
            students = db.query(Student).filter(Student.active.is_(True)).all()
        elif request.target == "inactive":
            students = db.query(Student).filter(Student.active.is_(False)).all()
        elif request.target == "both":
            students = db.query(Student).all()
        else:
            raise ValueError("Invalid target")

        for student in students:
            is_active = _check_attendance_threshold(
                student.cti_id, request.active_start, request.activity_thresholds, db
            )
            student.active = is_active

    db.commit()

def _check_attendance_threshold(
    cti_id: int,
    active_start: datetime,
    activity_thresholds: Dict[str, List[str]],
    db: Session
) -> bool:
    last_session_types = activity_thresholds.get("last_attended_session", [])
    if not last_session_types:
        return False

    attended_count = db.query(StudentAttendance).join(Attendance).filter(
        StudentAttendance.cti_id == cti_id,
        Attendance.session_start >= active_start,
        Attendance.session_type.in_(last_session_types)
    ).count()

    return attended_count > 0
