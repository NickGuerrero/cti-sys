from typing import List, Tuple, Dict

from sqlalchemy.orm import Session
from sqlalchemy import delete

from src.database.postgres.models import MissingAttendance, StudentAttendance


def insert_attendance(
    db: Session,
    cti_id: int,
    session_id: int,
    peardeck_score: float,
    full_attendance: bool,
) -> None:
    """
    Insert a new StudentAttendance record with the given fields.
    Assumes no existing row for (cti_id, session_id).
    """
    db.add(
        StudentAttendance(
            cti_id=cti_id,
            session_id=session_id,
            peardeck_score=peardeck_score,
            full_attendance=full_attendance,
        )
    )


def delete_missing(db: Session, email: str, session_id: int) -> None:
    """
    Delete the MissingAttendance row for (email, session_id).
    """
    db.execute(
        delete(MissingAttendance).where(
            MissingAttendance.email == email,
            MissingAttendance.session_id == session_id
        )
    )


def process_matches(
    db: Session,
    matches: List[Tuple[MissingAttendance, int]]
) -> List[Dict[str, any]]:
    """
    Process matches of MissingAttendance and cti_id.
    This function iterates through each match and performs the following:
        1. For each (MissingAttendance row, cti_id):
        2. If no StudentAttendance exists for (cti_id, session_id), insert it,
        then delete the MissingAttendance row and record.
        3. If a StudentAttendance exists, do nothing.
        4. Returns a list of dicts for each row actually moved:
            {"email": <str>, "name": <str>, "cti_id": <int>}.
    """
    moved_rows: List[Dict[str, any]] = []

    # Iterate through each match of MissingAttendance and cti_id
    for missing_row, cti_id in matches:
        sid = missing_row.session_id

        # Safe defaults if any fields are None
        score = missing_row.peardeck_score if missing_row.peardeck_score is not None else 0.0
        full_att = missing_row.full_attendance if missing_row.full_attendance is not None else False 


        # Check if StudentAttendance already exists for (cti_id, session_id)
        existing = (
            db.query(StudentAttendance)
            .filter_by(cti_id=cti_id, session_id=sid)
            .first()
        )

        # If no existing record, insert new StudentAttendance
        if not existing:
            insert_attendance(db, cti_id, sid, score, full_att)
            delete_missing(db, missing_row.email, sid)

            # Record the moved row details
            moved_rows.append({
                "email": missing_row.email,
                "name": missing_row.name,
                "cti_id": cti_id
            })
        # else: leave MissingAttendance untouched

    return moved_rows
