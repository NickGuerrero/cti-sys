from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.engine import Engine
from sqlalchemy.dialects.postgresql import array_agg
from src.database.postgres.models import Student, Accelerate, StudentEmail, CanvasID, AccountabilityGroup, Ethnicity
# import mongo objects here
import gspread
import pandas
from os import environ
from src.config import settings

# TODO: Move this into a general utilities file
# This was put here intially, since we didn't expect to have GSheet operations outside this class
def create_credentials():
    """
    Create GSheet credentials from an environment variable

    Production use only, normally you could have the credentials file in your project
    Deploying with Heroku requires the credentials be placed somewhere else. Make sure
    the below env vars are set before use

    """
    credentials = {
        "type": "service_account",
        "project_id": settings.gs_project_id,
        "private_key_id": settings.gs_private_key_id,
        "private_key": settings.gs_private_key,
        "client_email": settings.gs_client_email,
        "client_id": settings.gs_client_id,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": settings.gs_509_cert_url,
        "universe_domain": "googleapis.com"
    }
    gc = gspread.service_account_from_dict(credentials)
    return gc


def write_to_gsheet(data: pandas.DataFrame, worksheet_name: str,
                    gc: gspread.client.Client, sh: str):
    """
    Write a pandas dataframe to a Google Sheet
    
    @param data: The pandas Dataframe. Headers are written as the first row
    @param worksheet_name: The name of the worksheet in the Google Sheet
    @param gc: The Gspread client, uses credentials set-up prior
    @param sh: The Google Sheet ID (Retrieved from the URL)
    """
    # Important: Enable both Google Drive and Google Sheet API for the key
    sh = gc.open_by_key(settings.roster_sheet_key)
    worksheet = sh.worksheet(worksheet_name)
    worksheet.update([data.columns.values.tolist()] + data.values.tolist())
    return {
        "success": True,
        "worksheet_updated": worksheet_name,
        "rows_updated": len(data)
    }

def fetch_roster(eng: Engine):
    """
    Fetch roster from associated Accelerate tables, and return it as a pd dataframe
    @param eng: A SQLAlchemy Engine object that connects to the database

    Settings configuration (config.py)
    gsheet_write_rows_max: The maximum numbers of rows that can be written to gsheet
    (WARNING: Do not leave this unbounded. Keep max sheet size in mind when adjusting)

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
        .limit(settings.gsheet_write_rows_max) # No more than 999 rows on 1 sheet without issues
    )
    roster_frame = pandas.read_sql(roster_query, eng)

    # Create an empty dataframe to pad the resultant dataframe
    # This only pads rows, since gsheet writes only write over the existing sheet
    # Column padding is not common, should not be required often 
    empty_rows = max(settings.gsheet_write_rows_max - roster_frame.shape[0], 0)
    empty_data = {col: [pandas.NA for row in range(empty_rows)] for col in roster_frame.columns}
    padding = pandas.DataFrame(empty_data)
    pandas.concat([roster_frame, padding])

    # Dataframe needs to be modified to be copied to Google Sheet. Mostly allowing serialization.
    roster_frame = roster_frame.astype({"Birthday": str}) # Date objects not allowed
    roster_frame['Ethnicities'] = roster_frame['Ethnicities'].apply(
            lambda x: ', '.join(x) if isinstance(x, list) else (x if pandas.notnull(x) else "")
        ) # Lists not allowed
    roster_frame = roster_frame.fillna('') # Empty cells (na) not allowed, replaced with empty strings
    return roster_frame
