from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from os import environ
import gspread

from src.config import settings
from src.database.postgres.core import make_session
from src.database.postgres.core import engine as CONN
import src.gsheet.refresh.main.service as service
import src.gsheet.utils as utils

router = APIRouter()

@router.post("/",
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
            gc = utils.create_credentials()
            return utils.write_to_gsheet(roster_data, "Main Roster", gc, settings.roster_sheet_key)
        else:
            gc = gspread.service_account(filename='gspread_credentials.json')
            return utils.write_to_gsheet(roster_data, "Main Roster", gc, settings.test_sheet_key)

    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))