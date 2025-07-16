from datetime import datetime
from typing import Dict

import requests
import pandas as pd
from urllib.parse import urlparse, parse_qs
from sqlalchemy.orm import Session
from sqlalchemy import func
import io
from fastapi import BackgroundTasks
from src.config import settings
from src.database.postgres.models import (
    Attendance, StudentEmail, MissingAttendance, StudentAttendance
)
from sqlalchemy.exc import SQLAlchemyError
from src.utils.email import send_email

def send_email_notification(
    to_email: str, 
    subject: str, 
    html_body: str
) -> None:
    """
    Wrap the real send_email so background-task failures never bubble up.
    This is used to send email notifications for attendance processing.
    """
    try:
        send_email(to_email, subject, html_body)
    except Exception:
        pass

def process_attendance(
    db: Session,
    background_tasks: BackgroundTasks,
) -> Dict[str, int]:
    """
    Process unprocessed Attendance records with link_type='PearDeck':
    - Query all Attendance records where last_processed_date is None and link_type is 'PearDeck'.
    - For each record:
        - Attempt to process the record.
        - On success, commit the transaction and increment sheets_processed.
        - On failure, rollback the transaction and increment sheets_failed.
    - Return a dictionary containing the counts of processed and failed sheets.
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
            process_attendance_record(record, db=db, background_tasks=background_tasks)
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

def process_attendance_record(
    attendance_record: Attendance,
    db: Session,
    background_tasks: BackgroundTasks,
) -> None:
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
            db=db,
            background_tasks=background_tasks,
        )

    attendance_record.last_processed_date = datetime.now()

def process_attendance_row(
    row_data: pd.Series,
    df_columns: pd.Index,
    session_id: int,
    db: Session,
    background_tasks: BackgroundTasks,
) -> None:
    """
    Processes a single row of attendance data:
    
    - If the email column is empty, this row is skipped entirely.
    - Otherwise, we compute a Pear Deck score from the ratio of answered slides 
      to total slides (slides are any column name that starts with 'Slide ').
    - If the email matches an existing student, update a student_attendance record.
    - If the email is not found, inserts a missing_attendance record.
    """

    # Get email and name, skipping the row if there's no email
    email = str(row_data["Email"]).strip().lower()
    name = str(row_data["Name"]).strip()
    if not email:
        return  # No email, skip entirely

    # Only consider columns that start with "Slide "
    slide_columns = [col for col in df_columns if col.startswith("Slide ")]

    # Count only answers that are not blank or 'nan'
    answered_count = 0
    for col in slide_columns:
        val = str(row_data.get(col, "")).strip().lower()
        # If val isn't empty or 'nan', we count it as answered
        if val and val != "nan":
            answered_count += 1

    total_slides = len(slide_columns)
    peardeck_score = answered_count / total_slides if total_slides else 0.0
    session_score = peardeck_score
    attended_minutes = -1

    # Attempt to find the student by email
    email_record = (
        db.query(StudentEmail)
          .filter(func.lower(StudentEmail.email) == email)
          .first()
    )

    if not email_record:
        # If there's no matching student, insert into missing_attendance
        missing = MissingAttendance(
            email=email,
            session_id=session_id,
            name=name,
            peardeck_score=peardeck_score,
            attended_minutes=attended_minutes
        )
        db.merge(missing)
        background_tasks.add_task(
            send_email_notification,
            email,
            "Attendance email not found - please update",
            f"""
            <p>Hi {name},</p>
            <p>We couldn't find <strong>{email}</strong> in our records.</p>
            <p>Please <a href="https://docs.google.com/forms/d/e/1FAIpQLSe6KnTqeAi_VwAZ2yKl6-Zuu2w0Jedi9dr0KDRd2c6YKrfTjA/viewform">
               click here</a> to submit your correct email address.</p>
            """
        )
    else:
        # Otherwise, update or insert the student's attendance
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

    # If gid is not found in query, check the fragment
    # This is common in Google Sheets URLs
    if not gid_value and parsed.fragment:
        frag_params = parse_qs(parsed.fragment)
        if "gid" in frag_params and len(frag_params["gid"]) > 0:
            gid_value = frag_params["gid"][0]

    if not gid_value:
        gid_value = "0"

    # Construct the CSV export URL
    # Default gid is 0 if not found
    return f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid_value}"

