from datetime import datetime
from typing import Annotated, Optional
from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field

# https://www.mongodb.com/developer/languages/python/python-quickstart-fastapi/#database-models

# required to properly encode bson ObjectId to str on Mongo documents
PyObjectId = Annotated[str, BeforeValidator(str)]

class ApplicationBase(BaseModel):
    email: EmailStr = Field(description="An email address unique to each applicant")
    lname: str
    fname: str

    model_config = ConfigDict(extra="allow")

class ApplicationCreate(ApplicationBase):
    pass
    
class ApplicationModel(ApplicationBase):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    app_submitted: datetime

class DeepWork(BaseModel):
    day: str = Field(description="Weekday of the deepwork session")
    time: str = Field(description="Times for start and end of the deepwork session")
    sprint: str = Field(description="Which sprint this deepwork session is associated with")
    
class AccelerateFlexBase(BaseModel):
    cit_id: int = Field(description="ID for student across all db domains")
    selected_deep_work: list[DeepWork] = Field(description="Deepwork sessions selected for expected attendance")
    academic_goals: list[str] = Field(description="Student's expected academic outcomes")
    phone: str = Field(description="Student's phone number")
    academic_year: str = Field(description="Applicant's year in school")
    grad_year: int = Field(description="Student's expected graduation year")
    summers_left: int = Field(description="Number of summers the applicant has left before graduation")
    cs_exp: bool = Field(description="Whether the student has CS/programming experience")
    cs_courses: list[str] = Field(description="List of the CS classes the student has taken")
    math_courses: list[str] = Field(description="List of math classes the student as taken")
    program_expectation: str = Field(description="What the student is aiming to get out of the program")
    career_outlook: str = Field(description="Where the student sees themselves in 2-4 years")
    heard_about: str = Field(description="How the student heard about Accelerate")
    
    model_config = ConfigDict(extra="allow")

class AccelerateFlexModel(AccelerateFlexBase):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)

class PathwayGoalBase(BaseModel):
    pathway_goal: str = Field(description="Name for the pathway goal")
    pathway_desc: str = Field(description="Description of the pathway goal")
    course_req: str = Field(description="Courses required for the pathway goal")

class PathwayGoalModel(PathwayGoalBase):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)

class CourseBase(BaseModel):
    course_id: str = Field(description="Name or codeword for course")
    canvas_id: int = Field(description="ID of course as it exists on Canvas")
    title: str = Field(description="Title of the course")
    milestones: list[int] = Field(description="List of the number of assignments required for each milestone")
    version: str = Field(description="Version number of the course")

class CourseModel(CourseBase):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
