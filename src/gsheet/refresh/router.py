from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from os import environ
import gspread

from src.config import settings
from src.database.postgres.core import make_session
from src.database.postgres.core import engine as CONN
from src.gsheet.refresh.attendance.router import router as attendance_router
from src.gsheet.refresh.main.router import router as main_router

router = APIRouter()

router.include_router(
    main_router,
    prefix="/main"
)

router.include_router(
    attendance_router,
    prefix="/attendance"
)
