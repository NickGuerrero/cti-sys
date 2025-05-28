from fastapi import APIRouter

from .assign_sa.router import router as assign_sa_router
# Import other accelerate-related routers as needed
# For example:
# from .assign_sa_all.router import router as assign_sa_all_router
# from .process_attendance.router import router as process_attendance_router

router = APIRouter()

# Include the assign-sa router
router.include_router(assign_sa_router, prefix="/assign-sa")

# Include other accelerate-related routers as needed
# For example:
# router.include_router(assign_sa_all_router, prefix="/assign-sa-all")
# router.include_router(process_attendance_router, prefix="/process-attendance")a