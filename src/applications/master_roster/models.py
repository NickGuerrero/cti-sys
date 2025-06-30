from datetime import date
from typing import List, Optional
from pydantic import ConfigDict, Field

from src.applications.models import ApplicationModel

class ApplicationWithMasterProps(ApplicationModel):
    canvas_id: int
    pname: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    returning: Optional[bool] = Field(default=None)
    institution: Optional[str] = Field(default=None)
    birthday: Optional[date] = Field(default=None)
    ca_region: Optional[str] = Field(default=None)
    academic_year: Optional[str] = Field(default=None)
    grad_year: Optional[int] = Field(default=None)
    summers_left: Optional[int] = Field(default=None)
    cs_exp: Optional[bool] = Field(default=None)
    cs_courses: Optional[List[str]] = Field(default=None)
    math_courses: Optional[List[str]] = Field(default=None)
    program_expectation: Optional[str] = Field(default=None)
    career_outlook: Optional[str] = Field(default=None)
    academic_goals: Optional[List[str]] = Field(default=None)
    financial_need: Optional[List[str]] = Field(default=None)
    first_gen: Optional[bool] = Field(default=None)
    gender: Optional[str] = Field(default=None)
    race_ethnicity: Optional[List[str]] = Field(default=None) # TODO needs to be interpretted
    heard_about: Optional[str] = Field(default=None)

    model_config = ConfigDict(extra="allow")
