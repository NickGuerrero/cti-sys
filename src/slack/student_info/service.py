from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.postgres.models import Student, StudentEmail

def fetch_student_info(db: Session, user_email: str):

    select_stmt = select(
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
        StudentEmail.email).join(StudentEmail).where(StudentEmail.email == user_email)   
    
    result = db.execute(select_stmt).first()

    if result is None:
        raise HTTPException(status_code=404, detail=f"No student records found for email {user_email}")
    
    return result._asdict()
