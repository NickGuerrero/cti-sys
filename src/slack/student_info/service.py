from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.database.postgres.models import Student, StudentEmail

def fetch_student_info(db: Session, user_email: str):
    Email = StudentEmail

    select_stmt = (
        select(
            Student.cti_id,
            Student.fname,
            Student.lname,
            Student.pname,
            Student.institution,
            Student.target_year,
            Student.join_date,
            Student.gender,
            Student.ethnicities_agg,
            Student.birthday,
            Student.first_gen,
            # primary email (single value)
            func.max(Email.email).filter(Email.is_primary.is_(True)).label("primary_email"),
            # alternate emails (array)
            func.array_remove(
                func.array_agg(Email.email).filter(Email.is_primary.is_(False)),
                None
            ).label("alternate_emails"),
        )
        .join(Email, Email.cti_id == Student.cti_id)
        .where(Student.cti_id == (
            select(Email.cti_id).where(Email.email == user_email).scalar_subquery()
        ))
        .group_by(Student.cti_id)
    )
    result = db.execute(select_stmt).first()

    if result is None:
        raise HTTPException(status_code=404, detail=f"No student records found for email {user_email}")
    
    return result._asdict()
