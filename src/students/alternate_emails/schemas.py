from typing import List, Optional
from pydantic import BaseModel, EmailStr

class AlternateEmailRequest(BaseModel):
    alt_emails: Optional[List[EmailStr]] = []
    primary_email: Optional[str] = ""
    remove_emails: Optional[List[EmailStr]] = []
    google_form_email: EmailStr
