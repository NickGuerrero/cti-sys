from fastapi import APIRouter, Depends

from src.applications.router import router as applications_router
from src.applications.canvas_export.router import router as canvas_export_router
from src.applications.master_roster.router import router as applications_add_to_master_roster_router
from src.students.alternate_emails.router import router as student_alternate_emails_router
from src.students.attendance_log.router import router as student_attendance_log_router
from src.students.accelerate.process_attendance.router import router as accelerate_attendance_record_router
from src.students.accelerate.check_activity.router import router as accelerate_activity_check_router
from src.students.missing_students.router import router as student_recover_attendance_router
from src.students.attendance_entry.router import router as student_attendance_entry_router
from src.students.withdrawal_processing.router import router as student_withdrawal_router

from src.gsheet.refresh.router import router as gsheet_refresh_router
from src.utils.authorization import verify_api_key

api_router = APIRouter(dependencies=[Depends(verify_api_key)])

# /api/applications/...
api_router.include_router(
    applications_router,
    prefix="/applications",
    tags=["Applications"],
)

# /api/applications/master-roster...
api_router.include_router(
    applications_add_to_master_roster_router,
    prefix="/applications/add-to-master-roster",
    tags=["Applications"],
)

# /api/applications/canvas-export
api_router.include_router(
    canvas_export_router,
    prefix="/applications/canvas-export",
    tags=["Applications"],
)

# /api/students/alternate-emails
api_router.include_router(
    student_alternate_emails_router,
    prefix="/students/alternate-emails",
    tags=["Students"],
)

# /api/students/process-attendance-log
api_router.include_router(
    student_attendance_log_router,
    prefix="/students/process-attendance-log",
    tags=["Students"],
)

# /api/accelerate/process-attendance
api_router.include_router(
    accelerate_attendance_record_router,
    prefix="/students/accelerate/process-attendance",
    tags=["Accelerate"],
)

# /api/students/accelerate/check-activity
api_router.include_router(
    accelerate_activity_check_router,
    prefix="/students/accelerate/check-activity",
    tags=["Accelerate"],
)

# /api/students/recover-attendance
api_router.include_router(
    student_recover_attendance_router,
    prefix="/students/recover-attendance",
    tags=["Students"],
)

# /api/students/create-attendance-entry
api_router.include_router(
    student_attendance_entry_router,
    prefix="/students/create-attendance-entry",
    tags=["Students"],
)

# /api/students/process-withdrawal
api_router.include_router(
    student_withdrawal_router,
    prefix="/students/process-withdrawal",
    tags=["Students"],
)

# /api/gsheet/refresh/...
api_router.include_router(
    gsheet_refresh_router,
    prefix="/gsheet/refresh",
    tags=["GSheet"],
)