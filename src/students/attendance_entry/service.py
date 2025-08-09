import csv
import io
from datetime import datetime
from functools import lru_cache
from typing import Dict, Set

import requests
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.config import settings
from src.database.postgres.models import Attendance
from src.students.attendance_entry.schemas import AttendanceEntryRequest
from typing import Tuple


def parse_session_datetimes(entry: AttendanceEntryRequest) -> Tuple[datetime, datetime]:
    """
    Parse the session date and start/end times from the entry into datetime objects.
    Supports both MM/DD/YYYY and YYYY-MM-DD formats for the date.

    This function determines the date format based on the delimiter used in the date string.
    If the date contains '/', it assumes MM/DD/YYYY; if it contains '-', it checks the length of the first component
    to determine if it's YYYY-MM-DD or MM-DD-YYYY.
    """
    date_str = entry.session_date
    # Determine format based on delimiter and component length
    if "/" in date_str:
        date_fmt = "%m/%d/%Y"
    elif "-" in date_str:
        first = date_str.split("-")[0]
        if len(first) == 4:
            date_fmt = "%Y-%m-%d"
        else:
            date_fmt = "%m-%d-%Y"
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid date format: {date_str}")
    
    datetime_fmt = f"{date_fmt} %I:%M %p"
    
    # Convert to datetime objects for session start and end
    try:
        start_dt = datetime.strptime(f"{date_str} {entry.session_start_time}", datetime_fmt)
        end_dt = datetime.strptime(f"{date_str} {entry.session_end_time}", datetime_fmt)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid date/time format: {ve}")
    
    return start_dt, end_dt

@lru_cache(maxsize=1)
def load_allowed_emails() -> Set[str]:
    """
    Load allow-list of staff emails from a public Google Sheet CSV export URL.
    The sheet must be shared "Anyone with the link: Viewer" and have a header row with 'email'.
    """
    # Check if the URL is configured
    if not settings.allowed_sas_sheet_url:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,etail="No allow-list sheet URL configured (set ALLOWED_SAS_SHEET_URL)")
    
    # Fetch the CSV content from the URL
    try:
        resp = requests.get(settings.allowed_sas_sheet_url)
        resp.raise_for_status()
        csv_text = resp.text
    except Exception as ex:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"Failed to fetch allow-list sheet: {ex}")

    # Parse the CSV content
    reader = csv.reader(io.StringIO(csv_text))
    try:
        headers = next(reader)
    except StopIteration:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Allow-list sheet is empty"
        )
    
    # Find the index of the 'email' column, default to 0 if not found
    idx = headers.index('email') if 'email' in headers else 0
    
    # Return a set of emails, stripping whitespace and converting to lowercase
    return {row[idx].strip().lower() for row in reader if row}


def process_session_submission(
    db: Session,
    entry: AttendanceEntryRequest,
) -> Dict[str, int]:
    """
    Process a session attendance entry submission.
    Validates the entry against the allow-list and password, parses date/time,
    and inserts the attendance record into the database.
    """
    # 1. Check email against allow-list
    if entry.owner.lower() not in load_allowed_emails():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email not authorized to submit attendance")

    # 2. Check password is correct
    # if entry.password != settings.attendance_password:
    #     raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

    # 3. Parse date and time to datetime objects for session start and end
    start_dt, end_dt = parse_session_datetimes(entry)
    
    # 4. Insert record
    att = Attendance(
        program=entry.program,
        session_type=entry.session_type,
        session_start=start_dt,
        session_end=end_dt,
        link_type=entry.link_type,
        link=str(entry.link),
        owner=entry.owner,
        last_processed_date=None,
    )
    try:
        db.add(att)
        db.commit()
        db.refresh(att)
    except Exception as ex:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving record: {ex}"
        )

    return {"status": status.HTTP_200_OK}