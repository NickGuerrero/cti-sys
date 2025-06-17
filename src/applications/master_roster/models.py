from datetime import date
from typing import List, Optional

from pydantic import ConfigDict, Field
from src.applications.models import ApplicationModel

class ApplicationWithMasterProps(ApplicationModel):
    canvas_id: int
    pname: Optional[str] = Field(description="")
    phone: Optional[str]
    returning: Optional[bool]
    institution: Optional[str]
    birthday: Optional[date]
    ca_region: Optional[str] # NOTE this is missing in the database
    academic_year: Optional[str]
    grad_year: Optional[int]
    summers_left: Optional[int]
    cs_exp: Optional[bool]
    cs_courses: Optional[List[str]]
    math_courses: Optional[List[str]]
    program_expectation: Optional[str]
    career_outlook: Optional[str]
    academic_goals: Optional[List[str]]
    financial_need: Optional[List[str]] # NOTE not attribute of AccelerateFlexBase
    first_gen: Optional[bool]
    gender: Optional[str]
    race_ethnicity: Optional[List[str]] # TODO needs to be interpretted
    heard_about: Optional[str]

    model_config = ConfigDict(extra="allow") # NOTE allow for flexability of application?
