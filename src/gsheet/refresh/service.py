from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session, Engine
from sqlalchemy.dialects.postgresql import array_agg
from src.database.postgres.models import Student, Accelerate, StudentEmail, CanvasID, AccountabilityGroup, Ethnicity
from src.database.postgres.core import engine as CONN
# import mongo objects here
import gspread
import pandas
from os import environ

def write_to_gsheet(data: pandas.DataFrame, worksheet_name: str):
    # Important: Enable both Google Drive and Google Sheet API for the key
    gc = gspread.service_account(filename='gspread_credentials.json')
    sh = gc.open_by_key(environ.get("ROSTER_SHEET_KEY"))
    worksheet = sh.worksheet(worksheet_name)
    worksheet.update([data.columns.values.tolist()] + data.values.tolist())
    return {
        "success": True,
        "worksheet_updated": worksheet_name,
        "rows_updated": len(data)
    }

def sync_roster():
    pass
def fetch_roster(eng: Engine):
    """
    Fetch roster from associated Accelerate tables, and return it as a pd dataframe
    @param eng: A SQLAlchemy Engine object that connects to the database

    Notes:
    - pandas runs the query, so an Engine object is needed. Allowable for a Select query
    - The dataframe headers will match the sheet headers
    """
    roster_query = (
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
    roster_frame = pandas.read_sql(roster_query, eng)

    # Dataframe needs to be modified to be copied to Google Sheet. Mostly allowing serialization.
    roster_frame = roster_frame.astype({"Birthday": str}) # Date objects not allowed
    roster_frame['Ethnicities'] = roster_frame['Ethnicities'].apply(lambda x: ', '.join(x)) # Lists not allowed
    roster_frame = roster_frame.fillna('') # Empty cells (na) not allowed, replaced with empty strings
    return roster_frame

    pass
def fetch_attendance():
    pass
