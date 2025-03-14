from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.models import PyObjectId

# mongo models...
class ApplicationBase(BaseModel):
    email: EmailStr = Field(description="An email address unique to each applicant")
    lname: str
    fname: str

    model_config = ConfigDict(extra="allow")

class ApplicationModel(ApplicationBase):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    app_submitted: datetime
