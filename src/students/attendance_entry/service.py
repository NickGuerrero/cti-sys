import csv
import io
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, Optional, Set, Tuple

import requests
import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from gspread_dataframe import get_as_dataframe

from src.config import settings
from src.gsheet.refresh.service import create_credentials
from src.database.postgres.models import Attendance
from src.students.attendance_entry.schemas import AttendanceEntryRequest
from urllib.parse import urlparse, parse_qs

def detect_date_format(date_str: str) -> str:
    """
    Detect which date format to use based on delimiters and component length.
    Accepts:  MM/DD/YYYY, MM-DD-YYYY, or YYYY-MM-DD
    """
    date_str = date_str.strip()
    if "/" in date_str:
        return "%m/%d/%Y"
    if "-" in date_str:
        first = date_str.split("-", 1)[0]
        return "%Y-%m-%d" if len(first) == 4 else "%m-%d-%Y"
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Invalid date format: {date_str!r}",
    )


def parse_datetime(date_part: str, time_part: str, date_fmt: str) -> datetime:
    """
    Try multiple time formats and return a datetime or raise HTTP 400.
    12-hour time with AM/PM, 24-hour time with seconds, 24-hour time without seconds.
    """
    time_formats = ("%I:%M %p", "%H:%M:%S", "%H:%M")  # 12h, 24h
    last_err: Optional[Exception] = None
    for tf in time_formats:
        try:
            return datetime.strptime(f"{date_part.strip()} {time_part.strip()}", f"{date_fmt} {tf}")
        except ValueError as exc:
            last_err = exc
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Invalid date/time format: {date_part} {time_part} ({last_err})",
    )


def parse_session_datetimes(entry: AttendanceEntryRequest) -> Tuple[datetime, datetime]:
    """
    Accepts dates in:  MM/DD/YYYY, MM-DD-YYYY, or YYYY-MM-DD
    Accepts times in:  '6:00 PM', '08:00 PM', '18:00', '18:00:00'
    """
    date_fmt = detect_date_format(entry.session_date)
    start_dt = parse_datetime(entry.session_date, entry.session_start_time, date_fmt)
    end_dt = parse_datetime(entry.session_date, entry.session_end_time, date_fmt)

    if end_dt <= start_dt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_end_time must be after session_start_time",
        )
    return start_dt, end_dt


def normalize_google_sheet_url(raw_url: str) -> str:
    """
    Normalize a Google Sheets URL to its CSV export form.
    If the input is already an export URL, return it unchanged.
    If it's an edit/view link, rewrite it to export?format=csv&gid=<gid>.
    """
    if "docs.google.com/spreadsheets" not in raw_url:
        return raw_url  # not a Google Sheets URL, just return as-is

    if "export" in raw_url:
        return raw_url  # already normalized

    parsed = urlparse(raw_url)
    parts = parsed.path.split("/")
    try:
        sheet_id = parts[3]  # /spreadsheets/d/<sheet_id>/
    except IndexError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Google Sheet URL: {raw_url}",
        )

    qs = parse_qs(parsed.query)
    gid = qs.get("gid", ["0"])[0]

    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"

@lru_cache(maxsize=1)
def load_email_whitelist(sheet_key=settings.roster_sheet_key, worksheet=settings.sa_whitelist) -> Set[str]:
    """
    Fetch the allow-list from the Main Roster
    Expect a header row that includes an 'email' column
    Caches the result in memory for the process lifetime
    """
    # Fetch the whitelist directly from the Main Roster
    gc = create_credentials()
    sh = gc.open_by_key(sheet_key)
    whitelist = sh.worksheet(worksheet)
    # Convert it into a set for the cache
    df = get_as_dataframe(whitelist)
    return set(df["email"])


@lru_cache(maxsize=1)
def load_allowed_emails() -> Set[str]:
    """
    Fetch the allow-list from a public Google Sheet CSV.
    Expects a header row that includes an 'email' column.
    Caches the result in memory for the process lifetime.
    """
    raw_url = (settings.allowed_sas_sheet_url or "").strip()
    if not raw_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfigured: ALLOWED_SAS_SHEET_URL is not set",
        )

    url = normalize_google_sheet_url(raw_url)

    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "cti-attendance/1.0"})
        resp.raise_for_status()
        text = resp.content.decode("utf-8-sig")
    except Exception as ex:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch allow-list sheet: {ex}",
        )

    reader = csv.reader(io.StringIO(text))
    try:
        headers = next(reader)
    except StopIteration:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Allow-list sheet is empty",
        )

    lower_map = {h.strip().lower(): i for i, h in enumerate(headers)}
    idx = lower_map.get("email", 0)

    emails = set()
    for row in reader:
        if not row or idx >= len(row):
            continue
        val = (row[idx] or "").strip().lower()
        if val:
            emails.add(val)
    return emails


def process_session_submission(db: Session, entry: AttendanceEntryRequest) -> Dict[str, Any]:
    """
    Insert a single attendance session record.
    Upstream router handles API-key auth.
    This function validates the allow-list and input data.

    Steps:
    1. Check if entry.owner is in the allow-list.
    2. Parse and validate session date/times.
    3. Insert into the database.
    """
    if entry.owner.lower().strip() not in load_email_whitelist(): # TODO
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not authorized to submit attendance",
        )

    start_dt, end_dt = parse_session_datetimes(entry)

    att = Attendance(
        program=entry.program.strip(),
        session_type=entry.session_type.strip(),
        session_start=start_dt,
        session_end=end_dt,
        link_type=entry.link_type.strip(),
        link=str(entry.link),
        owner=entry.owner.strip(),
        last_processed_date=None,
    )

    try:
        db.add(att)
        db.commit()
        db.refresh(att)
    except Exception as ex:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving record: {ex}",
        )

    return {
        "status": status.HTTP_200_OK,
        "session_id": getattr(att, "session_id", None),
        "owner": att.owner,
        "session_start": att.session_start.isoformat(sep=" ", timespec="seconds"),
        "session_end": att.session_end.isoformat(sep=" ", timespec="seconds"),
        "link": att.link,
    }
