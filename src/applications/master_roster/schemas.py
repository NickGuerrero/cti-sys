from pydantic import BaseModel, EmailStr, Field

class MasterRosterCreateRequest(BaseModel):
    applicant_email: EmailStr = Field(description="Email of applicant submitting commitment")

class MasterRosterCreateResponse(BaseModel):
    status: int
    message: str
