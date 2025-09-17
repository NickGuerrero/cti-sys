from pydantic import BaseModel, EmailStr, HttpUrl

class AttendanceEntryRequest(BaseModel):
    owner: EmailStr
    program: str
    session_type: str
    session_date: str
    session_start_time: str 
    session_end_time: str
    link_type: str
    link: HttpUrl
