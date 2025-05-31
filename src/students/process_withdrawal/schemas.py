from typing import List, Optional
from pydantic import BaseModel, EmailStr

class ProcessWithdrawalRequest(BaseModel):
    auto_email: EmailStr
    fname: str
    lname: str
