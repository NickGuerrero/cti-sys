from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from src.models import PyObjectId

# mongo models...
class CourseBase(BaseModel):
    course_id: str = Field(description="Name or codeword for course")
    canvas_id: Optional[int] = Field(default=None, description="ID of course as it exists on Canvas")
    title: Optional[str] = Field(default=None, description="Title of the course")
    milestones: Optional[List[int]] = Field(default=None, description="List of the number of assignments required for each milestone")
    version: Optional[str] = Field(default=None, description="Version number of the course")

    model_config = ConfigDict(extra="forbid")

class CourseModel(CourseBase):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
