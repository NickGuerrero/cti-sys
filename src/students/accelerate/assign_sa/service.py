# src/students/accelerate/assign_sa/service.py
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, List, Optional

from src.database.postgres.models import Student, AccountabilityGroup, Accelerate

def assign_student_SA(student_id: int, db: Session, overwrite: bool, sa: Optional[str] = None, exclude_list: Optional[List[str]] = None) -> Dict:
    """
    Assigns a student to a Student Accelerator (SA) while balancing groups.
    
    :param student_id: ID of the student being assigned an SA.
    :param db: Database session.
    :param overwrite: If True, allows reassignment of an existing SA.
    :param sa: (Optional) Directly assigns a specific SA.
    :param exclude_list: (Optional) List of SAs to exclude from assignment.
    :return: Response dictionary following API structure.
    """
    
    exclude_list = exclude_list if exclude_list else []
    
    # Fetch the student
    student = db.query(Student).filter(Student.cti_id == student_id).first()
    if not student:
        return {"status": 404, "message": f"Student with ID {student_id} not found."}
    
    # Ensure the student has an Accelerate record
    accelerate_record = student.accelerate_record
    if not accelerate_record:
        return {"status": 400, "message": "Student is not part of the Accelerate program."}
    
    # Check if student already has an SA
    current_sa = None
    if accelerate_record.accountability_group:
        ag_record = accelerate_record.ag_record
        if ag_record:
            current_sa = ag_record.student_accelerator
    
    # If student already has an SA and overwrite is False, return an error
    if current_sa and not overwrite:
        return {"status": 400, "message": f"Student already has an assigned SA ({current_sa}) and overwrite is False."}
    
    # Fetch all available SAs and their student counts
    sa_counts = (
        db.query(
            AccountabilityGroup.student_accelerator,
            func.count(Accelerate.cti_id).label("current_count")
        )
        .outerjoin(Accelerate, AccountabilityGroup.ag_id == Accelerate.accountability_group)
        .group_by(AccountabilityGroup.student_accelerator)
        .all()
    )
    
    if not sa_counts:
        return {"status": 404, "message": "No Student Accelerators found in the system."}
    
    # Convert SA data into a dictionary for easy access
    sa_dict = {sa_name: count for sa_name, count in sa_counts}
    
    # If a specific SA was provided, verify it exists
    if sa:
        if sa not in sa_dict:
            return {"status": 404, "message": f"Specified SA '{sa}' not found in the database."}
        if sa in exclude_list:
            return {"status": 400, "message": f"Specified SA '{sa}' is in the exclude list."}
    else:
        # Filter out excluded SAs
        filtered_sas = {name: count for name, count in sa_dict.items() if name not in exclude_list}
        
        if not filtered_sas:
            return {"status": 400, "message": "No available SAs to assign the student."}
        
        # Assign the SA with the fewest students
        sa = min(filtered_sas, key=filtered_sas.get)
    
    # Find the SA group
    sa_group = db.query(AccountabilityGroup).filter(AccountabilityGroup.student_accelerator == sa).first()
    if not sa_group:
        return {"status": 404, "message": f"SA '{sa}' not found in the database."}
    
    try:
        # Assign the student to the SA
        accelerate_record.accountability_group = sa_group.ag_id
        
        # Update accountability team (using the same group ID for now)
        accelerate_record.accountability_team = sa_group.ag_id
        
        # Commit the changes
        db.commit()
        
        return {
            "status": 200, 
            "message": f"Successfully assigned student to SA '{sa}'", 
            "assigned_sa": sa,
            "group_name": sa_group.group_name,
            "ag_id": sa_group.ag_id
        }
    except Exception as e:
        db.rollback()
        return {"status": 500, "message": f"Database error occurred: {str(e)}"}