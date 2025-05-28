# src/students/accelerate/assign_sa/router.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session


from src.database.postgres.core import make_session
from .service import assign_student_SA

router = APIRouter()

class SAAssignmentRequest(BaseModel):
    overwrite: bool = False
    sa: Optional[str] = None
    exclude_list: Optional[List[str]] = None

class SAAssignmentResponse(BaseModel):
    status: int
    message: str
    assigned_sa: Optional[str] = None
    group_name: Optional[str] = None
    ag_id: Optional[int] = None

@router.put("/{student_id}", response_model=SAAssignmentResponse)
async def assign_student_accelerator(
    student_id: int,
    request: SAAssignmentRequest,
    db: Session = Depends(make_session)
):
    """
    Assign a student to a Student Accelerator (SA), either specified or automatically based on load balancing.
    
    Parameters:
    - student_id: The ID of the student to assign
    - overwrite: If true, allows changing an existing SA assignment
    - sa: Optional specific SA to assign the student to
    - exclude_list: Optional list of SAs to exclude from automatic assignment
    
    Returns:
    - Assignment status information and details of the assigned SA
    """
    
    result = assign_student_SA(
        student_id=student_id,
        db=db,
        overwrite=request.overwrite,
        sa=request.sa,
        exclude_list=request.exclude_list
    )
    
    # If result status is not 200, raise appropriate HTTP exception
    if result["status"] != 200:
        raise HTTPException(
            status_code=result["status"],
            detail=result["message"]
        )
    
    # Return successful result
    return result