from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, EmailStr

class ApplicationCreate(BaseModel):
    email: EmailStr
    lname: str
    fname: str
    app_submitted: datetime

    model_config = ConfigDict(extra="allow", json_encoders={ObjectId: str})
