from pydantic import BaseModel, EmailStr, HttpUrl

class AttendanceEntryRequest(BaseModel):
    owner: EmailStr
    program: str
    session_type: str
    session_date: str  # format: MM-DD-YYYY
    session_start_time: str  # format: HH:MM AM/PM
    session_end_time: str  # format: HH:MM AM/PM
    link_type: str
    link: HttpUrl
    password: str