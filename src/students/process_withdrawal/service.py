from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database.postgres.models import StudentEmail, InactiveRequest
from src.students.process_withdrawal.schemas import ProcessWithdrawalRequest
from typing import List, Optional, Dict, Any
import random
import string
from datetime import datetime, timedelta, timezone

def process(*, request: ProcessWithdrawalRequest, db: Session) -> Dict[str, Any]:
    """
    Main entry point to process withdrawal request.
    """
    # Step 1:Check if auto_email or manual_email is primary_email 
    google_form_email = request.auto_email
    
    # Query for primary email from auto_email
    email_record = db.query(StudentEmail).filter(
        func.lower(StudentEmail.email) == google_form_email
    ).first()

    if not email_record:
        raise HTTPException(status_code=404, detail="Student not found")

    # Retrieve the student's unique identifier.
    cti_id = email_record.cti_id

    # Query for all emails associated with this student.
    all_emails = db.query(StudentEmail).filter(StudentEmail.cti_id == cti_id).all()

    primary_email = None
    # Build a list of emails and identify the primary email.
    for e in all_emails:
        if e.is_primary:
            primary_email = e.email
            break
    
    # Make sure google form email and primary email matches
    if primary_email != google_form_email:
        raise HTTPException(
            status_code=403,
            detail="Primary email must match the email used to submit the form."
        )

    # Step 2: Generate new link with a one-time password (OTP)
    student_cti_id = cti_id
    otp = int(''.join(random.choices(string.digits, k=16)) + str(student_cti_id)) # In future: come up with a more secure generation of OTP
    create_timestamp = datetime.now(timezone.utc)
    withdrawal_link = f"/api/students/{student_cti_id}/mark-inactive?key={otp}"
    
    # Step 3: Store withdrawal record and timestamp in inactive_requests  
    new_inactive_record = InactiveRequest(
        passkey=otp,
        id=student_cti_id,
        created=create_timestamp
    )
    db.add(new_inactive_record)
    db.commit()

    return withdrawal_link

def fetch_inactive_record(google_form_email: str, db: Session) -> Dict[str, Any]:
    """
    Retrieve the withdrawal record associated with the student identified by the given Google Form email.

    This function performs a case-insensitive search for the student's withdrawal record,
    then fetches all associated emails—including the primary email—and returns them in a dictionary
    for easy JSON conversion. It is primarily used for testing.
    """
    default_return = {"id": None, "passkey": None, "timestamp": None}
    # fetch student id associated with google form email

    email_record = db.query(StudentEmail).filter(
        func.lower(StudentEmail.email) == google_form_email
    ).first()

    if not email_record:
        return default_return

    # Retrieve the student's unique identifier.
    cti_id = email_record.cti_id

    # Query for the withdrawal record using a case insensitive match.
    withdrawal_record = db.query(InactiveRequest).filter(
        func.lower(InactiveRequest.id) == cti_id
    ).first()

    if not withdrawal_record:
        return default_return

    return {
        "id": withdrawal_record.id,
        "passkey": withdrawal_record.passkey,
        "timestamp": withdrawal_record.created
    }
