from fastapi import HTTPException
from sqlalchemy import select, func, cast
from sqlalchemy.orm import Session
from sqlalchemy.engine import Engine
from sqlalchemy.dialects.postgresql import array_agg

from src.database.postgres.models import Attendance, StudentAttendance, StudentEmail
import gspread
import pandas
import numpy as np
from typing import List, Dict
from datetime import date
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

def fetch_group_attendance(eng: Engine, start_date: date, end_date: date, cti_ids: Dict[int, str]):
    """
    Fetch attendance records and create an attendance matrix of select cti_ids and a date range,
    given the associated Accelerate tables
    @param eng: A SQLAlchemy Engine object that connects to the database
    """
    if not cti_ids:
        return pandas.DataFrame(columns=["cti_id", "email"])

    # 1) Build cti_id -> email mapping, defaulting to "NOT FOUND"
    id_to_email = fetch_cti_emails(eng, cti_ids)

    # 2) Build base CTI/email frame
    cti_data = pandas.DataFrame(
        [{"cti_id": cid, "email": id_to_email.get(cid, "NOT FOUND")} for cid in cti_ids]
    ).set_index("cti_id")

    # 3) Build date columns
    dates = pandas.date_range(start_date, end_date)
    date_grid = np.zeros((len(cti_ids), len(dates)), dtype=bool)
    pandas_grid = pandas.DataFrame(date_grid, index=cti_data.index, columns=dates)

    result_grid = pandas.concat([cti_data, pandas_grid], axis=1)

    # 4) Fetch attendance for those CTI IDs and date range
    attendance_query = (
        select(
            StudentAttendance.cti_id,
            cast(Attendance.session_start, date).label("session_date"),
        )
        .join(Attendance, Attendance.session_id == StudentAttendance.session_id)
        .where(StudentAttendance.cti_id.in_(cti_ids))
        .where(Attendance.session_start.between(start_date, end_date))
    )

    attendance_frame = pandas.read_sql(attendance_query, eng)
    if attendance_frame.empty:
        return result_grid

    attendance_frame["session_date"] = pandas.to_datetime(attendance_frame["session_date"])

    # 5) Mark True where there was attendance
    for row in attendance_frame.itertuples(index=False):
        # row.cti_id, row.session_date
        if row.cti_id in result_grid.index and row.session_date in result_grid.columns:
            result_grid.loc[row.cti_id, row.session_date] = True

    return result_grid

def fetch_cti_ids_from_sheet(spreadsheet_id: str, worksheet_name: str, gc: gspread.client.Client) -> List[int]:
    sh = gc.open_by_key(spreadsheet_id)
    worksheet = sh.worksheet(worksheet_name)

    headers = worksheet.row_values(1)
    headers = [header.strip().lower() for header in headers]

    try:
        column_index = headers.index("cti_id") + 1
    except ValueError:
        print("Column name not found")
        return
    
    column_values = worksheet.col_values(column_index)

    data = []

    for value in column_values[1:]:
        if value:
            try:
                data.append(int(value))
            except ValueError:
                # Skip
                continue
    
    return data

def fetch_cti_emails(eng: Engine, cti_ids: List[int]) -> Dict[int, str]:
    ids_to_email = dict.fromkeys(cti_ids, "NOT FOUND")

    attendance_query = (
        select(
            StudentEmail.cti_id,
            StudentEmail.email
        )
        .where(StudentEmail.cti_id.in_(cti_ids))
    )

    email_frame = pandas.read_sql(attendance_query, eng)
    for row in email_frame.iterrows():
        ids_to_email[row.cti_id] = row.email

    return ids_to_email