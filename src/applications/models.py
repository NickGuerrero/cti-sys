from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.models import PyObjectId

# mongo models...
class ApplicationBase(BaseModel):
    email: EmailStr = Field(description="An email address unique to each applicant")
    lname: str
    fname: str

    model_config = ConfigDict(extra="allow")

class ApplicationBatchOperation(Enum):
    """
    Different operations to be enacted on Application collection documents.
    """
    UNTERVIEW_CANVAS_ENROLLMENT: 1
    ADD_TO_MASTER: 2

class ApplicationBatchUpdate(BaseModel):
    """
    todo: revisit
    Accounts for the different batch operations.

    Example operations: Unterview/Canvas enrollment, add to Master Roster, etc.
    """
    operation: ApplicationBatchOperation
    date: datetime

class ApplicationModel(ApplicationBase):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    app_submitted: datetime
    last_batch_update: Optional[ApplicationBatchUpdate] = Field(default=None) # todo: revisit``
    canvas_id: Optional[int] = Field(default=None, description="Canvas ID of applicant, added after export")
    added_unterview_course: bool = Field(default=False, description="Whether the applicant has accessed the Unterview course")
    next_steps_sent: bool = Field(default=False, description="Whether the applicant has been sent the Next Steps email")
    accessed_unterview: bool = Field(default=False)
    commitment_quiz_completed: bool = Field(default=False)
    master_added: bool = Field(default=False)
