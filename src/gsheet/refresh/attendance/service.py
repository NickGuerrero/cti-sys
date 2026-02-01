from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.engine import Engine
from sqlalchemy.dialects.postgresql import array_agg

from src.database.postgres.models import Attendance
import gspread
import pandas
from src.config import settings

def fetch_attendance(eng: Engine):
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
    attendance_query = (
        select(
            Attendance.session_id.label("Session ID"),
            Attendance.session_start.label("Start Date"),
            Attendance.session_end.label("End Date"),
            Attendance.program.label("Program"),
            Attendance.session_type.label("Session Type"),
            Attendance.link.label("Link"),
            Attendance.owner.label("Owner"),
            Attendance.last_processed_date.label("Processed On"),
            Attendance.student_count.label("Student Count")
        )
        .order_by(Attendance.session_start.asc()) # Earliest to latest
        .limit(settings.gsheet_write_rows_max) # No more than 999 rows on 1 sheet without issues
    )
    attendance_frame = pandas.read_sql(attendance_query, eng)

    # Create an empty dataframe to pad the resultant dataframe
    # This only pads rows, since gsheet writes only write over the existing sheet
    # Column padding is not common, should not be required often 
    empty_rows = max(settings.gsheet_write_rows_max - attendance_frame.shape[0], 0)
    empty_data = {col: [pandas.NA for row in range(empty_rows)] for col in attendance_frame.columns}
    padding = pandas.DataFrame(empty_data)
    pandas.concat([attendance_frame, padding])

    # Dataframe needs to be modified to be copied to Google Sheet. Mostly allowing serialization.
    attendance_frame = attendance_frame.astype({
        "Start Date": str,
        "End Date": str,
        "Processed On": str}) # Date objects not allowed
    attendance_frame = attendance_frame.fillna('') # Empty cells (na) not allowed, replaced with empty strings
    return attendance_frame