from pydantic import BaseModel, ConfigDict, EmailStr
from typing import List, Optional
from datetime import datetime, date

# postgres models...
class BaseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class StudentEmailDTO(BaseDTO):
    email: EmailStr
    is_primary: bool

class StudentDTO(BaseDTO):
    cti_id: int
    fname: str
    pname: Optional[str] = None
    lname: str
    join_date: datetime
    target_year: int
    gender: Optional[str] = None
    first_gen: Optional[bool] = None
    institution: Optional[str] = None
    is_graduate: Optional[bool] = False
    birthday: Optional[date] = None
    active: bool
    cohort_lc: bool
    email_addresses: List[StudentEmailDTO]
