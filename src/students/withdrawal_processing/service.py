from typing import Any, Dict
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.database.postgres.models import Student, Accelerate, StudentEmail


def process_withdrawal_form(db: Session, email: str) -> Dict[str, Any]:
    """
    Deactivates the student and all related records with an 'active' field.
    For now, this includes Student and Accelerate records.
    """
    # Look up student via email
    email_entry = db.execute(
        select(StudentEmail).where(StudentEmail.email == email)
    ).scalar_one_or_none()

    if not email_entry:
        return {"status": 404, "message": f"No student found with email: {email}"}

    student = db.query(Student).filter(Student.cti_id == email_entry.cti_id).first()
    if not student:
        return {"status": 404, "message": f"No student record found for email: {email}"}

    # Flip all active flags to False
    student.active = False

    if student.accelerate_record:
        student.accelerate_record.active = False

    db.flush()

    return {
        "status": 200,
        "message": f"Student {student.fullname} (CTI ID: {student.cti_id}) and all related records have been deactivated.",
        "email": email,
    }
