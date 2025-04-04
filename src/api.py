from fastapi import APIRouter

from src.applications.router import router as applications_router
from src.applications.canvas_export.router import router as canvas_export_router
from src.students.alternate_emails.router import router as student_alternate_emails_router

api_router = APIRouter()

# /api/applications/...
api_router.include_router(
    applications_router,
    prefix="/applications",
    tags=["Applications"]
)

api_router.include_router(
    canvas_export_router,
    prefix="/applications/canvas-export",
    tags=["Applications"]
)

# /api/students/...
api_router.include_router(
    student_alternate_emails_router,
    prefix="/students/alternate-emails",
    tags=["Students"]
)
