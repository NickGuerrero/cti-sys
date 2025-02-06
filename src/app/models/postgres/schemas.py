from pydantic import BaseModel, ConfigDict

class ORMSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class StudentSchema(ORMSchema):
    cti_id: int
    fname: str
    pname: str
    lname: str
    join_date: str # TODO Validate date
    target_year: int
    gender: str
    first_gen: bool
    institution: str
    is_graduate: bool
    birthday: str # TODO Validate date
    active: bool
    cohort_lc: bool