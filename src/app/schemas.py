from pydantic import BaseModel, ConfigDict

class ORMSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class StudentSchema(ORMSchema):
    id: int
    fname: str