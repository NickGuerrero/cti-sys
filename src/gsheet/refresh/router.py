from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from os import environ
import gspread

from src.config import settings
from src.database.postgres.core import make_session
from src.database.postgres.core import engine as CONN
import src.gsheet.refresh.service as service

router = APIRouter()

@router.post("/main",
    description="Refresh main roster information on the associated Google Sheet",
    response_description="Updated main roster",
    status_code=status.HTTP_201_CREATED)
def refresh_main(db: Session = Depends(make_session)) -> Dict[str, Any]:
    """
    Copy database records to the specified Google Sheet (Main Roster)
    """
    try:
        # Pull roster & write to sheet
        roster_data = service.fetch_roster(CONN)
        if settings.app_env == "production":
            gc = service.create_credentials()
            return service.write_to_gsheet(roster_data, "Main Roster", gc, environ.get("ROSTER_SHEET_KEY"))
        else:
            gc = gspread.service_account(filename='gspread_credentials.json')
            return service.write_to_gsheet(roster_data, "Main Roster", gc, environ.get("ROSTER_SHEET_KEY"))

    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
