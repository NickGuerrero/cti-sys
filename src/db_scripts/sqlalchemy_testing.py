from src.app.database import SessionFactory
from src.app.models.postgres.models import *

from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from datetime import datetime

"""
Here's a collection of examples to show you how to use SQLAlchemy in this project
Use the docs for a complete reference: https://docs.sqlalchemy.org/en/20/index.html
Make sure CTI_POSTGRES_URL is set before running the script
"""
# Note that sessions are handled differently in endpoints, see main.py
with SessionFactory() as cur_session:
    try:
        # Example Create
        # Note that this uses the ORM method because Creates are very straightforward
        # Meanwhile, please use select(), update(), and delete() for RUD operations
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
            # Note we can specify entries to other tables if they have a defined relationship
            # FK gets automatically assigned in this process, so this can be a neat way to do this
            email_addresses=[
                StudentEmail(email="janedoe@email.com", is_primary=False),
                StudentEmail(email="janedoe@gmail.com", is_primary=True)],
            canvas_id=CanvasID(canvas_id=100),
            ethnicities=[Ethnicity(ethnicity="Hispanic or Latino")]
        )
        cur_session.add(new_student) # Execute the create statement
        cur_session.flush() # Send changes to the database, use to synch with following db operations
        
        # Example Reads: We use query-builder with session.select()

        # SELECT * FROM students WHERE cti_id = 100;
        # This will fetch the entire object as is. You can modify the object directly if you need
        select_stmt1 = select(Student).where(Student.cti_id == 100)

        # SELECT cti_id, fname, lname FROM students ORDER BY cti_id ASC LIMIT 10;
        # The columns will be returned as a tuple and is NOT tied to the object
        select_stmt2 = select(Student.cti_id, Student.fname, Student.lname).order_by(Student.cti_id).limit(10)

        # SELECT * FROM students INNER JOIN student_emails ON students.cti_id = student_emails.cti_id
        # WHERE student_emails.is_primary = True ORDER BY students.cti_id DESC LIMIT 10;
        # From my understanding, you shouldn't need to do explicit joins often, but this is how you can do it
        select_stmt3 = (
            select(Student, StudentEmail)
            .join(Student.email_addresses)
            .where(StudentEmail.is_primary == True)
            .order_by(Student.cti_id.desc()).limit(10)
        )

        # To run the queries, you need to execute it through a session, as shown below
        # Each execution generates a Result object, accessing it varies on what you're fetching

        # What unique() does is unify rows, i.e. on a join, only 1 row have can have the same PK
        # This is applied on the result from execute() and must be explicit
        # We need this because models have eager-loaded relationship in models, so unique() must used
        # See: https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html#joined-eager-loading
        result1 = cur_session.execute(select_stmt1).unique()
        result2 = cur_session.execute(select_stmt2).unique()
        result3 = cur_session.execute(select_stmt3).unique()

        # Result overview: https://docs.sqlalchemy.org/en/20/core/connections.html#sqlalchemy.engine.Result
        # Objects need to be fetched from Result, here I use scalar_one_or_none() & all()
        # NOTE: Once fetched, Result is closed, make sure to store the results if you need to keep it
        example = result1.scalar_one_or_none()
        print(example, example.cti_id) # Print 1 result, or None if no result is returned
        print(result2.all()) # Return a list of row objects, result2 is now empty

        # For the joined query, the joined objects are returned as tuples
        # Here I unpack them so it's easier to see the separation
        for st, em in result3.all():
            print(st.fname, st.lname, em.email, em.is_primary)

        # Example Update
        # UPDATE students SET target_year = 2026 WHERE cti_id = 100;
        simple_update_stmt = (
            update(Student)
            .where(Student.cti_id == 100)
            .values(target_year=2026)
        )

        # Before
        pre_update_res = cur_session.execute(select_stmt1).unique().scalar_one()
        print(pre_update_res.cti_id, pre_update_res.target_year)
        # After - Note that unique() is only used for SELECT, not UPDATE
        cur_session.execute(simple_update_stmt)
        post_update_res = cur_session.execute(select_stmt1).unique().scalar_one()
        print(post_update_res.cti_id, post_update_res.target_year)

        # Example Delete
        # DELETE FROM students WHERE cti_id = 100;
        simple_delete_stmt = (
            delete(Student)
            .where(Student.cti_id == 100)
        )
        cur_session.execute(simple_delete_stmt)

        # scalar_one_or_none() returns None here
        result = cur_session.execute(select_stmt1).scalar_one_or_none()
        print(result)

        # At the end of your queries, you need to commit your changes
        # Do not try auto-commit (& auto-flush), please be explicit with db synch
        # cur_session.commit()
        # It's commented out here so you don't modify the database with this script
    finally:
        # Undo the session and restore database to its original state
        cur_session.rollback() # Rollbacks uncommitted changes
        cur_session.close()