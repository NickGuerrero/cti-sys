from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database.postgres.models import Student, StudentEmail
from src.students.alternate_emails.schemas import AlternateEmailRequest

def modify(*, request: AlternateEmailRequest, db: Session) -> None:
    # Normalize all emails to lowercase and strip whitespace
    google_form_email = request.google_form_email.strip().lower()
    request_primary_email = request.primary_email.strip().lower() if request.primary_email else None
    request.alt_emails = [email.strip().lower() for email in request.alt_emails]
    request.remove_emails = [email.strip().lower() for email in request.remove_emails]

    # Find student by Google Form email
    student_email_entry = db.query(StudentEmail).filter(
        func.lower(StudentEmail.email) == google_form_email
    ).first()

    # Check if student was found
    if not student_email_entry:
        raise HTTPException(status_code=404, detail="Student not found")

    student = db.query(Student).filter(Student.cti_id == student_email_entry.cti_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Fetch all student emails and normalize to lowercase for comparisons
    student_emails = db.query(StudentEmail).filter(StudentEmail.cti_id == student.cti_id).all()
    student_email_dict = {email.email.lower(): email for email in student_emails} 
    student_email_list = set(student_email_dict.keys())
    
    # Ensure primary email change authentication
    if request_primary_email:
        # If changing primary email, it must match the Google form email
        if request_primary_email != google_form_email:
            raise HTTPException(
                status_code=403,
                detail="Primary email must match the email used to submit the form"
            )

    # Handle email removal
    for email_lower in request.remove_emails:
        if email_lower not in student_email_list:
            continue 

        # Prevent removal of primary email unless a new primary is specified
        if student_email_dict[email_lower].is_primary and not request_primary_email:
            raise HTTPException(
                status_code=403,
                detail=f"Cannot remove primary email: {email_lower} without specifying a new primary email"
            )

        # Delete the email
        db.query(StudentEmail).filter(
            StudentEmail.cti_id == student.cti_id,
            func.lower(StudentEmail.email) == email_lower
        ).delete()
        student_email_list.remove(email_lower)

    # Ensure new alternate emails do not belong to another student
    for email_lower in request.alt_emails:
        if email_lower in request.remove_emails:
            continue
            
        if email_lower not in student_email_list:
            # Check if email belongs to another student
            email_owner = db.query(StudentEmail).filter(
                func.lower(StudentEmail.email) == email_lower
            ).first()
            
            if email_owner and email_owner.cti_id != student.cti_id:
                raise HTTPException(
                    status_code=403,
                    detail=f"Email '{email_lower}' is already associated with another student"
                )
                
            # Add new email
            new_email = StudentEmail(email=email_lower, cti_id=student.cti_id, is_primary=False)
            db.add(new_email)
            student_email_list.add(email_lower)

    # Handle primary email update
    if request_primary_email:
        db.query(StudentEmail).filter(StudentEmail.cti_id == student.cti_id).update({"is_primary": False})
        
        # Set the requested email as primary
        db.query(StudentEmail).filter(
            StudentEmail.cti_id == student.cti_id,
            func.lower(StudentEmail.email) == request_primary_email
        ).update({"is_primary": True})

    db.commit()
