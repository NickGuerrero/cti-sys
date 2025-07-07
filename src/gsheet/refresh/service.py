from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import array_agg
from src.database.postgres.models import Student, Accelerate, StudentEmail, CanvasID, AccountabilityGroup, Ethnicity
# import mongo objects here

def connect_gspread():
    pass
def sync_roster():
    pass
def fetch_roster(db: Session):
    """
    Fetch roster data from associated Accelerate tables, and return ???
    """
    roster_info = (
        select(
            Student.cti_id.label("CTI ID"),
            StudentEmail.email.label("Primary Email Address"),
            Student.fullname.label("Student Name"),
            Student.birthday.label("Birthday"),
            Accelerate.returning_student.label("Returning"),
            AccountabilityGroup.group_name.label("Accountability Group"),
            AccountabilityGroup.student_accelerator.label("Student Accelerator"),
            CanvasID.canvas_id.label("Canvas ID"),
            Student.ca_region.label("CA Region"),
            Student.gender.label("Gender"),
            Student.first_gen.label("First-Generation Student"),
            Student.institution.label("Academic Institution"),
            Student.ethnicities_agg.label("Ethnicities"),
            Accelerate.active.label("Active"),
            Accelerate.participation_score.label("Participation Score"),
            Accelerate.sessions_attended.label("Sessions Attended"),
            Accelerate.participation_streak.label("Attendance Streak"),
            Accelerate.inactive_weeks.label("Inactive Weeks")
        )
        .join(CanvasID, Student.cti_id == CanvasID.cti_id, isouter=True)
        .join(StudentEmail, Student.cti_id == StudentEmail.cti_id, isouter=True)
        .join(Accelerate, Student.cti_id == Accelerate.cti_id, isouter=True)
        .join(AccountabilityGroup, Accelerate.accountability_group == AccountabilityGroup.ag_id, isouter=True)
        .where(StudentEmail.is_primary == True)
        .order_by(Student.cti_id.asc())
        .limit(998) # No more than 999 rows on 1 sheet without issues
    )
    return roster_info

    pass
def fetch_attendance():
    pass
