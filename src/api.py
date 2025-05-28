from fastapi import APIRouter

from src.applications.router import router as applications_router
from src.students.alternate_emails.router import router as student_alternate_emails_router
from src.students.accelerate.assign_sa.router import router as student_assign_sa_router


api_router = APIRouter()

# /api/applications/...
api_router.include_router(
    applications_router,
    prefix="/applications",
    tags=["Applications"]
)

# /api/students/...
api_router.include_router(
    student_alternate_emails_router,
    prefix="/students/alternate-emails",
    tags=["Students"]
)
# /api/students/accekerate/assign-sa/...
api_router.include_router(
    student_assign_sa_router,
    prefix="/accelerate/students/assign-sa",
    tags=["Students"]
)