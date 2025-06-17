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
    last_batch_update: Optional[datetime] = Field(default=None, description="The last datetime at which the applicant was run within the Canvas Export")
    canvas_id: Optional[int] = Field(default=None, description="Canvas ID of applicant, added after export")
    added_unterview_course: bool = Field(default=False, description="Whether the applicant has accessed the Unterview course")
    next_steps_sent: bool = Field(default=False, description="Whether the applicant has been sent the Next Steps email")
    accessed_unterview: bool = Field(default=False, description="Whether the applicant has themselves accessed the Unterview course")
    commitment_quiz_completed: bool = Field(default=False, description="Whether the applicant has completed the Commitment Quiz")
    master_added: bool = Field(default=False, description="Whether the applicant has been added to the Master Roster")
