from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.postgres.models import Student, StudentEmail

def fetch_student_info(db: Session, user_email: str):
    """
    first_name Student.fname
    last_name Student.lname
    preferred_name Student.pname
    primary_email StudentEmail          !!
    institution Student.institution
    target_year Student.target_year
    join_date Student.join_date
    gender Student.gender
    ethnicity Student.ethnicities_agg   ??
    birthday Student.birthday
    first_generation Student.first_gen
    """

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
    
    results = db.execute(select_stmt).all()

    if len(results) == 0:
        raise ValueError("No student records found")
    
    if len(results) > 1:
        raise ValueError("Multiple student records found")
    
    return results[0]._asdict()
