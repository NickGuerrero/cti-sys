from fastapi import APIRouter

from src.applications.router import router as applications_router
from src.students.alternate_emails.router import router as student_alternate_emails_router
from src.students.activity.router import router as activity_router
from src.students.attendance_log.router import router as student_attendence_log_router

api_router = APIRouter()

# /api/applications/...
api_router.include_router(
    applications_router,
    prefix="/applications",
    tags=["Applications"]
)

# /api/students/alternate-emails...
api_router.include_router(
    student_alternate_emails_router,
    prefix="/students/alternate-emails",
    tags=["Students"]
)

# /api/students/activity
api_router.include_router(
    activity_router, 
    prefix="/students/activity", 
    tags=["Students"]
)

# /api/students/process-attendance-log...
api_router.include_router(
    student_attendence_log_router,
    prefix="/students/process-attendance-log",
    tags=["Students"]
)
