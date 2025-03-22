from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database.postgres.models import Student, StudentEmail
from src.students.alternate_emails.schemas import AlternateEmailRequest
from typing import List, Optional, Dict, Any

def fetch_current_emails(google_form_email: str, db: Session) -> Dict[str, Any]:
    """
    Retrieve all email addresses associated with the student identified by the given Google Form email.

    This function performs a case-insensitive search for the student's email record,
    then fetches all associated emails—including the primary email—and returns them in a dictionary
    for easy JSON conversion. It is primarily used for testing.
    """
    # Query for the email record using a case insensitive match.
    email_record = db.query(StudentEmail).filter(
        func.lower(StudentEmail.email) == google_form_email
    ).first()

    if not email_record:
        return {"emails": [], "primary_email": None}

    # Retrieve the student's unique identifier.
    cti_id = email_record.cti_id

    # Query for all emails associated with this student.
    all_emails = db.query(StudentEmail).filter(StudentEmail.cti_id == cti_id).all()

    primary_email = None
    email_list = []
    # Build a list of emails and identify the primary email.
    for e in all_emails:
        email_list.append(e.email)
        if e.is_primary:
            primary_email = e.email

    return {
        "emails": email_list,
        "primary_email": primary_email,
    }


def find_student_by_google_email(google_form_email: str, db: Session) -> Student:
    """
    Retrieve the student associated with the given Google Form email.

    This function locates the StudentEmail record using a case insensitive match, then retrieves
    the corresponding Student based on the student's unique identifier. If either record is missing,
    an HTTP 404 error is raised.
    """
    student_email_entry = db.query(StudentEmail).filter(
        func.lower(StudentEmail.email) == google_form_email
    ).first()

    if not student_email_entry:
        raise HTTPException(status_code=404, detail="Student not found")

    student = db.query(Student).filter(Student.cti_id == student_email_entry.cti_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    return student


def remove_student_email(
    student: Student,
    emails_to_remove: List[str],
    new_primary_email: Optional[str],
    db: Session,
) -> None:
    """
    Remove specified email addresses from the student's record.

    This function deletes emails listed in emails_to_remove. It prevents removal of the primary email
    unless a new primary email is provided, otherwise, it raises an HTTP error.
    """
    if not emails_to_remove:
        return

    # Fetch all emails associated with the student.
    student_emails = db.query(StudentEmail).filter(StudentEmail.cti_id == student.cti_id).all()
    student_email_dict = {email.email.lower(): email for email in student_emails}

    for email_lower in emails_to_remove:
        email_record = student_email_dict.get(email_lower)
        
        if not email_record:
            continue
    
        # if not email_record:
        #     raise HTTPException(
        #         status_code=404, 
        #         detail=f"Email '{email_lower}' not found for the student."
        #     )

        # Prevent removal of the primary email without specifying a new one.
        if email_record.is_primary and not new_primary_email:
            msg = f"Cannot remove primary email '{email_lower}' without specifying a new primary email."
            raise HTTPException(status_code=403, detail=msg)

        # Delete the email record.
        db.query(StudentEmail).filter(
            StudentEmail.cti_id == student.cti_id,
            func.lower(StudentEmail.email) == email_lower
        ).delete()


def add_alternate_emails(
    student: Student,
    alt_emails: List[str],
    removed_emails: List[str],
    db: Session,
) -> None:
    """
    Add new alternate email addresses to the student's record.

    This function adds each email in alt_emails that is not already associated with the student or
    scheduled for removal. It also verifies that the email is not already used by another student,
    raising an HTTP error if it is.
    """
    if not alt_emails:
        return

    # Retrieve all current emails for the student.
    student_email_records = db.query(StudentEmail).filter(
        StudentEmail.cti_id == student.cti_id
    ).all()

    existing_emails = {email.email.lower() for email in student_email_records}

    for email_lower in alt_emails:
        # Skip if it's in both add and remove lists or if student already has this email.
        if email_lower in removed_emails or email_lower in existing_emails:
            continue

        # Check if the email is already associated with another student.
        existing_owner = db.query(StudentEmail).filter(
            func.lower(StudentEmail.email) == email_lower
        ).first()

        if existing_owner and existing_owner.cti_id != student.cti_id:
            msg = f"Email '{email_lower}' is already associated with another student."
            raise HTTPException(status_code=403, detail=msg)

        # Add the new alternate email.
        new_email = StudentEmail(
            email=email_lower,
            cti_id=student.cti_id,
            is_primary=False,
        )
        db.add(new_email)


def update_primary_email(
    student: Student,
    request_primary_email: Optional[str],
    google_form_email: str,
    db: Session
) -> None:
    """
    Update the student's primary email address.

    The new primary email must match the normalized Google Form email. All existing email records are
    reset to non primary, and the record corresponding to the new primary email is updated.
    If the update fails (for example, if the email is not found), an HTTP error is raised.
    """
    if not request_primary_email:
        return

    if request_primary_email.lower() != google_form_email:
        raise HTTPException(
            status_code=403,
            detail="Primary email must match the email used to submit the form."
        )

    # Reset all emails for the student to non-primary.
    db.query(StudentEmail).filter(
        StudentEmail.cti_id == student.cti_id
    ).update({"is_primary": False})

    # Update the new primary email.
    updated_rows = db.query(StudentEmail).filter(
        StudentEmail.cti_id == student.cti_id,
        func.lower(StudentEmail.email) == request_primary_email.lower()
    ).update({"is_primary": True})

    if not updated_rows:
        msg = f"Could not set '{request_primary_email}' as primary (email not found)."
        raise HTTPException(status_code=404, detail=msg)
    
def modify(*, request: AlternateEmailRequest, db: Session) -> None:
    """
    Main entry point to modify alternate emails.
    """

    # Step 1: remove leading/trailing spaces and convert to lowercase.
    google_form_email = request.google_form_email.strip().lower()
    primary_email = request.primary_email.strip().lower() if request.primary_email else None
    alt_emails = [email.strip().lower() for email in request.alt_emails]
    remove_emails = [email.strip().lower() for email in request.remove_emails]

    # Step 2: Retrieve the student record using the normalized Google Form email.
    student = find_student_by_google_email(google_form_email, db)

    # Step 3: Remove emails from the student's record.
    # This ensures that emails flagged for removal are deleted, and if removing a primary email,
    # a new primary email must be specified.
    remove_student_email(
        student=student,
        emails_to_remove=remove_emails,
        new_primary_email=primary_email,
        db=db
    )

    # Step 4: Add any new alternate emails.
    # This step adds new emails while verifying that they are not already in use by another student.
    add_alternate_emails(
        student=student,
        alt_emails=alt_emails,
        removed_emails=remove_emails,
        db=db
    )

    # Step 5: Update the primary email if a new one is provided.
    update_primary_email(
        student=student,
        request_primary_email=primary_email,
        google_form_email=google_form_email,
        db=db
    )

    # Step 6: Commit all changes to the database.
    db.commit()
