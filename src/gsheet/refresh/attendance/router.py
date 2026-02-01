from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from os import environ
import gspread
from datetime import date, timedelta

from src.config import settings
from src.database.postgres.core import make_session
from src.database.postgres.core import engine as CONN
import src.gsheet.utils as utils
import src.gsheet.refresh.attendance.service as service

router = APIRouter()

@router.post("/",
    description="Refresh attendance information on the associated Google Sheet",
    response_description="Updated attendance roster",
    status_code=status.HTTP_201_CREATED)
def refresh_attendance(db: Session = Depends(make_session)) -> Dict[str, Any]:
    """
    Copy database records to the specified Google Sheet (Main Roster)
    """
    try:
        # Pull roster & write to sheet
        attendance_data = service.fetch_attendance(CONN)
        if settings.app_env == "production":
            gc = utils.create_credentials()
            return utils.write_to_gsheet(attendance_data, "Attendance", gc, settings.roster_sheet_key)
        else:
            gc = gspread.service_account(filename='gspread_credentials.json')
            return utils.write_to_gsheet(attendance_data, "Attendance", gc, settings.test_sheet_key)

    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/group-attendance",
    description="Load in attendance information given a group of IDs and a date range in the associated Google Sheet",
    response_description="Updated group attendance roster",
    status_code=status.HTTP_201_CREATED)
def refresh_group_attendance(spreadsheet_id: str, spreadsheet_name: str, start_date: Optional[date] = None, end_date: Optional[date] = None, db: Session = Depends(make_session)) -> Dict[str, Any]:
    """
    Copy database records of select students from a specified Google Sheet and record them onto the same Sheet given a date range
    """
    try:
        if not start_date or not end_date:
            end_date = date.today()
            start_date = end_date - timedelta(days=settings.default_attendance_lookback_days)

        if settings.app_env == "production":
            gc = utils.create_credentials()
            cti_ids = service.fetch_cti_ids_from_sheet(spreadsheet_id, spreadsheet_name, gc)
            key = settings.roster_sheet_key
        else:
            gc = gspread.service_account(filename='gspread_credentials.json')
            cti_ids = service.fetch_cti_ids_from_sheet(spreadsheet_id, spreadsheet_name, gc)
            key = settings.test_sheet_key

        # pass CTI IDs into the group attendance service
        attendance_data = service.fetch_group_attendance(CONN, start_date, end_date, cti_ids)

        return utils.write_to_gsheet(attendance_data, spreadsheet_name, gc, key)

    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    