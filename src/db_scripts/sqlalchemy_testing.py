from src.app.database import engine, Base, make_session, SessionFactory
from src.app.models.postgres.models import *

from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from datetime import datetime

"""
Here's a collection of examples to show you how to use SQLAlchemy in this project
Use the docs for a complete reference:
* Use query-builder strategies when possible
"""
# TODO: Fix delete
with SessionFactory() as cur_session:
    try:
        # Example Create
        # Note that this uses the ORM method because Creates are very straightforward
        # Meanwhile, select(), update(), and delete() for RUD operations
        # These allow for more explicit & complex queries
        new_student = Student(
            cti_id=100,
            fname="Jane",
            lname="Doe",
            target_year=2025,
            gender="Female",
            first_gen=True,
            institution="SJSU",
            is_graduate=False,
            birthday=datetime(2000, 11, 29),
            cohort_lc=False,
            email_addresses=[
                StudentEmail(email="janedoe@email.com", is_primary=False),
                StudentEmail(email="janedoe@gmail.com", is_primary=True)],
            canvas_id=CanvasID(canvas_id=100),
            ethnicities=[Ethnicity(ethnicity="Hispanic or Latino")]
        )
        cur_session.add(new_student)
        cur_session.flush()
        
        # Example Read
        basic_select_stmt = select(Student).where(Student.cti_id == 100)

        # A few other statements you can test on your own
        select_stmt1 = select(Student).order_by(Student.cti_id).limit(10)
        select_stmt2 = select(Student.fname, Student.lname).limit(10)
        join_stmt = (
            select(Student, StudentEmail)
            .join(StudentEmail.cti_id)
            .where(StudentEmail.is_primary == True)
            .order_by(Student.cti_id).limit(10)
        )
        result = cur_session.execute(basic_select_stmt)
        print(result)

        # Example Update
        simple_update_stmt = (
            update(Student)
            .where(Student.cti_id == 100)
            .values(target_year=2026)
        )
        cur_session.execute(simple_update_stmt)
        result = cur_session.execute(basic_select_stmt)
        print(result)

        # Example Delete
        # TODO: Delete doesn't cascade for some reason, likely problem in model definition
        simple_delete_stmt = (
            delete(Student)
            .where(Student.cti_id == 100)
        )
        cur_session.execute(simple_delete_stmt)
        result = cur_session.execute(basic_select_stmt)
        print(result)
    finally:
        # Undo the session and restore database to its original state
        cur_session.rollback()
        cur_session.close()