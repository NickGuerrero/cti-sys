from typing import List, Optional
from pydantic import BaseModel, EmailStr

class AlternateEmailRequest(BaseModel):
    alt_emails: List[EmailStr] = []
    primary_email: Optional[str] = None
    remove_emails: List[EmailStr] = []
    google_form_email: EmailStr
