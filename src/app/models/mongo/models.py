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
