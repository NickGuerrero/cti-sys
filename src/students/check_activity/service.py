from datetime import datetime
from typing import Dict, List
from sqlalchemy.orm import Session
from src.database.postgres.models import Student, Attendance, StudentAttendance, Accelerate

def process_student_activity(request, program: str, db: Session):
    # Fetch students by target
    if request.target == "active":
        students = db.query(Student).filter(Student.active.is_(True)).all()
    elif request.target == "inactive":
        students = db.query(Student).filter(Student.active.is_(False)).all()
    elif request.target == "both":
        students = db.query(Student).all()
    else:
        raise ValueError("Invalid target")
    
    # Program-specific activity check (Accelerate)
    if program == "accelerate":
        for student in students:
            acc_record = db.query(Accelerate).filter(Accelerate.cti_id == student.cti_id).first()
            if acc_record:
                acc_record.active = _check_attendance_threshold(
                    student.cti_id, request.active_start, request.activity_thresholds, db
                )
        # Set overall student.active based only on accelerate.active
        for student in students:
            acc_record = db.query(Accelerate).filter(Accelerate.cti_id == student.cti_id).first()
            if acc_record:
                student.active = acc_record.active
    
    # Default else for future programs
    else:
        # For now does nothing, placeholder for future programs
        pass
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
