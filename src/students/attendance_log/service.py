from datetime import datetime
from typing import Dict

import requests
import pandas as pd
from urllib.parse import urlparse, parse_qs
from sqlalchemy.orm import Session
from sqlalchemy import func
import io

from src.database.postgres.models import (
    Attendance, StudentEmail, MissingAttendance, StudentAttendance
)
from sqlalchemy.exc import SQLAlchemyError, NoResultFound

def process_attendance(db: Session) -> Dict[str, int]:
    """
    - Find all unprocessed Attendance records for link_type='PearDeck'.
    - For each record:
        - Try to process it
        - If it fails, rollback + sheets_failed += 1
        - If it succeeds, commit + sheets_processed += 1
    - Return a dict with final totals
    """
    unprocessed = (
        db.query(Attendance)
          .filter(Attendance.last_processed_date.is_(None))
          .filter(func.lower(Attendance.link_type) == "peardeck")
          .all()
    )

    sheets_processed = 0
    sheets_failed = 0

    for record in unprocessed:
        try:
            process_attendance_record(record, db=db)
            db.commit()
            sheets_processed += 1
        except (requests.RequestException, ValueError, SQLAlchemyError):
            db.rollback()
            sheets_failed += 1

    return {
        "status": 200,
        "sheets_processed": sheets_processed,
        "sheets_failed": sheets_failed
    }

def process_attendance_record(attendance_record: Attendance, db: Session) -> None:
    """
    Fetch the CSV data for this one Attendance record, parse each row, and
    update student_attendance or missing_attendance. If successful, mark last_processed_date.
    Raises exceptions on error.
    """
    df = fetch_csv_dataframe(attendance_record.link)

    for _, row in df.iterrows():
        process_attendance_row(
            row_data=row,
            df_columns=df.columns,
            session_id=attendance_record.session_id,
            db=db
        )

    # Mark as processed
    attendance_record.last_processed_date = datetime.now()

# def fetch_csv_dataframe(link: str) -> pd.DataFrame:
#     """
#     Converts a Google Sheet link to a CSV export link, fetches CSV,
#     returns a pandas DataFrame. Checks for 'Name' and 'Email' columns.
#     Raises ValueError if missing columns or fetch fails.
#     """
#     csv_url = convert_google_sheet_link_to_csv(link)
#     resp = requests.get(csv_url)
#     resp.raise_for_status()

#     # Parse CSV
#     df = pd.read_csv(resp.content.decode("utf-8"))
#     if "Name" not in df.columns or "Email" not in df.columns:
#         raise ValueError("Required columns (Name, Email) not found in CSV.")
#     return df

def fetch_csv_dataframe(link: str) -> pd.DataFrame:
    """
    Converts a Google Sheet link to a CSV export link, fetches CSV,
    returns a pandas DataFrame. Checks for 'Name' and 'Email' columns.
    Raises ValueError if missing columns or fetch fails.
    """

    # Fetch CSV from Google Sheets
    csv_url = convert_google_sheet_link_to_csv(link)
    resp = requests.get(csv_url)
    resp.raise_for_status()

    decoded_str = resp.content.decode("utf-8")

    # Read CSV from string
    df = pd.read_csv(io.StringIO(decoded_str))

    # Clean up column names with extra spaces
    df.columns = [col.strip() for col in df.columns]

    # Check for required columns
    if "Name" not in df.columns or "Email" not in df.columns:
        raise ValueError("Required columns (Name, Email) not found in CSV.")

    return df


def process_attendance_row(
    row_data: pd.Series,
    df_columns: pd.Index,
    session_id: int,
    db: Session
) -> None:
    """
    Given one row, calculates scores and updates either student_attendance or missing_attendance.
    """
    email = str(row_data["Email"]).strip().lower()
    name = str(row_data["Name"]).strip()

    # Identify the "slides" columns, everything after the first 3
    slides = df_columns[3:]
    answers = []
    for col in slides:
        val = str(row_data.get(col, "")).strip()
        answers.append(val)

    answered_count = sum(1 for ans in answers if ans)
    total_slides = len(answers)
    peardeck_score = float(answered_count) / total_slides if total_slides else 0.0
    session_score = peardeck_score
    attended_minutes = 0

    if not email:
        # No email then skip
        return

    # Attempt to find the student by email
    email_record = (
        db.query(StudentEmail)
          .filter(func.lower(StudentEmail.email) == email)
          .first()
    )

    if not email_record:
        # Insert missing attendance
        missing = MissingAttendance(
            email=email,
            session_id=session_id,
            name=name,
            peardeck_score=peardeck_score,
            attended_minutes=attended_minutes
        )
        db.merge(missing)
    else:
        # Found student -> upsert into student_attendance
        cti_id = email_record.cti_id
        existing_attendance = (
            db.query(StudentAttendance)
              .filter(
                  StudentAttendance.cti_id == cti_id,
                  StudentAttendance.session_id == session_id
              )
              .first()
        )
        if existing_attendance:
            existing_attendance.peardeck_score = peardeck_score
            existing_attendance.attended_minutes = attended_minutes
            existing_attendance.session_score = session_score
        else:
            new_attendance = StudentAttendance(
                cti_id=cti_id,
                session_id=session_id,
                peardeck_score=peardeck_score,
                attended_minutes=attended_minutes,
                session_score=session_score
            )
            db.add(new_attendance)

def convert_google_sheet_link_to_csv(link: str) -> str:
    """
    Convert a standard Google Sheets URL into a CSV export URL, e.g.
    https://docs.google.com/spreadsheets/d/<DOC_ID>/export?format=csv&gid=<GID>
    """
    parsed = urlparse(link)

    # Extract doc ID
    doc_id = None
    if "/d/" in parsed.path:
        try:
            after_d = parsed.path.split("/d/")[1]
            doc_id = after_d.split("/")[0]
        except IndexError:
            pass
    if not doc_id:
        raise ValueError(f"Unable to parse doc ID from: {link}")

    # Extract gid
    gid_value = None
    query_params = parse_qs(parsed.query)
    if "gid" in query_params and len(query_params["gid"]) > 0:
        gid_value = query_params["gid"][0]

    if not gid_value and parsed.fragment:
        frag_params = parse_qs(parsed.fragment)
        if "gid" in frag_params and len(frag_params["gid"]) > 0:
            gid_value = frag_params["gid"][0]

    if not gid_value:
        gid_value = "0"

    return f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid_value}"
