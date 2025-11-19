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
from src.utils.email import send_email as raw_send_email

import gspread
from src.gsheet.utils import create_credentials

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
        raw_send_email(to_email, subject, html_body)
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
        except (requests.RequestException, ValueError, SQLAlchemyError, Exception):
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
    attendance_record.student_count = len(df)

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
    
    # Check if first and last slide columns are not empty or 'nan'
    if total_slides >= 1:
        first_slide_val = str(row_data.get(slide_columns[0], "")).strip().lower()
        last_slide_val = str(row_data.get(slide_columns[-1], "")).strip().lower()
        full_att = bool(first_slide_val and first_slide_val != "nan" and last_slide_val and last_slide_val != "nan")
    else:
        full_att = False

    # Attempt to find the student by email
    email_record = (
        db.query(StudentEmail)
          .filter(func.lower(StudentEmail.email) == email)
          .first()
    )

    if not email_record:
        # Check if MissingAttendance already exists for this email and session
        existing_missing = (
            db.query(MissingAttendance)
            .filter(
                func.lower(MissingAttendance.email) == email,
                MissingAttendance.session_id == session_id
            )
            .first()
        )
        
        if not existing_missing:
            # If there's no matching student, insert into missing_attendance
            missing = MissingAttendance(
                email=email,
                session_id=session_id,
                name=name,
                peardeck_score=peardeck_score,
                full_attendance=full_att,
            )
            db.merge(missing)
        
        # Always send the email notification
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
            existing_attendance.full_attendance = full_att
        else:
            new_attendance = StudentAttendance(
                cti_id=cti_id,
                session_id=session_id,
                peardeck_score=peardeck_score,
                full_attendance=full_att,
            )
            db.add(new_attendance)

def fetch_csv_dataframe(link: str) -> pd.DataFrame:
    """
    Fetches the CSV data from the given Google Sheets link and returns it as a pandas DataFrame.
    It looks for the worksheet that contains "Name", "Email", and at least one "Slide " column.
    """
    # Authenticate with gspread
    if settings.app_env == "production":
        gc = create_credentials()
    else:
        gc = gspread.service_account(filename='gspread_credentials.json')
    
    spreadsheet = gc.open_by_url(link)
    
    # Check all worksheets to find the one with attendance data
    for worksheet in spreadsheet.worksheets():
        try:
            # Get all values from the worksheet
            all_values = worksheet.get_all_values()
            if not all_values:
                continue
            
            # Extract headers
            headers = [str(h).strip() for h in all_values[0]]
            
            # Check if this worksheet has the required columns
            has_name = "Name" in headers
            has_email = "Email" in headers
            has_slides = any(col.startswith("Slide ") for col in headers)
            
            if has_name and has_email and has_slides:
                # Convert to DataFrame 
                df = pd.DataFrame(all_values[1:], columns=headers)
                
                # Clean up column names with extra spaces
                df.columns = [col.strip() for col in df.columns]
                
                return df
                
        except Exception:
            continue
    
    # Fallback to first worksheet if no match found
    first_worksheet = spreadsheet.get_worksheet(0)
    all_values = first_worksheet.get_all_values()
    
    if not all_values:
        raise ValueError("Worksheet is empty.")
    
    df = pd.DataFrame(all_values[1:], columns=all_values[0])
    df.columns = [col.strip() for col in df.columns]
    
    # Check for required columns
    if "Name" not in df.columns or "Email" not in df.columns:
        raise ValueError("Required columns (Name, Email) not found in CSV.")
    
    return df