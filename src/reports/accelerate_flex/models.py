from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from src.models import PyObjectId

# mongo models...
class DeepWorkModel(BaseModel):
    day: str = Field(description="Weekday of the deepwork session")
    time: str = Field(description="Times for start and end of the deepwork session")
    sprint: str = Field(description="Which sprint this deepwork session is associated with")
    
class AccelerateFlexBase(BaseModel):
    cti_id: int = Field(description="ID for student across all db domains")
    selected_deep_work: Optional[List[DeepWorkModel]] = Field(default=None, description="Deepwork sessions selected for expected attendance")
    academic_goals: Optional[List[str]] = Field(default=None, description="Student's expected academic outcomes")
    phone: Optional[str] = Field(default=None, description="Student's phone number")
    academic_year: Optional[str] = Field(default=None, description="Applicant's year in school")
    grad_year: Optional[int] = Field(default=None, description="Student's expected graduation year")
    summers_left: Optional[int] = Field(default=None, description="Number of summers the applicant has left before graduation")
    cs_exp: Optional[bool] = Field(default=None, description="Whether the student has CS/programming experience")
    cs_courses: Optional[List[str]] = Field(default=None, description="List of the CS classes the student has taken")
    math_courses: Optional[List[str]] = Field(default=None, description="List of math classes the student as taken")
    program_expectation: Optional[str] = Field(default=None, description="What the student is aiming to get out of the program")
    career_outlook: Optional[str] = Field(default=None, description="Where the student sees themselves in 2-4 years")
    heard_about: Optional[str] = Field(default=None, description="How the student heard about Accelerate")
    
    model_config = ConfigDict(extra="allow")

class AccelerateFlexModel(AccelerateFlexBase):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
