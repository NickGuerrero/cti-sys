from fastapi import HTTPException
from sqlalchemy import select, func, cast, and_, Date
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
            cast(Attendance.session_start, Date).label("session_date"),
        )
        .join(Attendance, Attendance.session_id == StudentAttendance.session_id)
        .where(
            and_(StudentAttendance.cti_id.in_(cti_ids),
                 cast(Attendance.session_start, Date).between(start_date, end_date),
            )
        )
    )

    print(attendance_query)

    attendance_frame = pandas.read_sql(attendance_query, eng)
    print(attendance_frame)
    if not attendance_frame.empty:
        attendance_frame["session_date"] = pandas.to_datetime(attendance_frame["session_date"])

        for row in attendance_frame.itertuples(index=False):
            if row.cti_id in result_grid.index and row.session_date in result_grid.columns:
                result_grid.loc[row.cti_id, row.session_date] = True

    # From here on, ALWAYS normalize before returning
    final_df = result_grid.reset_index()

    # Normalize headers
    final_df.columns = [
        col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)
        for col in final_df.columns
    ]

    # Simple integer index
    final_df.index = range(len(final_df))

    # Everything as string so gspread/JSON is happy
    final_df = final_df.astype(str)

    return final_df

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
    
    worksheet.clear()
    
    return data

def fetch_cti_emails(eng: Engine, cti_ids: List[int]) -> Dict[int, str]:
    ids_to_email = dict.fromkeys(cti_ids, "NOT FOUND")

    attendance_query = (
        select(
            StudentEmail.cti_id,
            StudentEmail.email
        )
        .where(
            and_(
                StudentEmail.cti_id.in_(cti_ids),
                StudentEmail.is_primary
            )
        )
    )

    email_frame = pandas.read_sql(attendance_query, eng)
    for index, row in email_frame.iterrows():
        ids_to_email[row.cti_id] = row.email

    return ids_to_email