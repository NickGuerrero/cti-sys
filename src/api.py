from fastapi import APIRouter

from src.applications.router import router as applications_router
from src.applications.canvas_export.router import router as canvas_export_router
from src.students.alternate_emails.router import router as student_alternate_emails_router
from src.students.activity.router import router as activity_router
from src.students.attendance_log.router import router as student_attendence_log_router
from src.students.accelerate.process_attendance.router import router as accelerate_attendance_record_router
from src.students.missing_students.router import router as student_recover_attendance_router

api_router = APIRouter()

# /api/applications/...
api_router.include_router(
    applications_router,
    prefix="/applications",
    tags=["Applications"]
)

# /api/applications/canvas-export
api_router.include_router(
    canvas_export_router,
    prefix="/applications/canvas-export",
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

# /api/accelerate/process-attendance...
api_router.include_router(
    accelerate_attendance_record_router,
    prefix="/students/accelerate/process-attendance",
    tags=["Accelerate"]
)

# /api/students/recover-attendance...
api_router.include_router(
    student_recover_attendance_router,
    prefix="/students/recover-attendance",
    tags=["Students"]
)
