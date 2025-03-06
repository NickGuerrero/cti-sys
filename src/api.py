# include all domain routes & dependencies & configs on api router
from fastapi import APIRouter
from src.application.router import router as application_router

api_router = APIRouter()

api_router.include_router(
	application_router,
	prefix="/applications",
	tags=["applications"]
)
