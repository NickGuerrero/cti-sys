from pydantic import BaseModel, EmailStr

class WithdrawalRequest(BaseModel):
    email: EmailStr