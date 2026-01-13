# src/accelerate/service.py
from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, Iterable, List, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.database.postgres.models import Accelerate, Attendance, StudentAttendance

def process_accelerate_metrics(db: Session) -> Dict[str, int]:
    """
    Process every active Accelerate record and store fresh participation metrics.

    Steps performed:
    1. Fetch rows in accelerate where active is True.
    2. Pull raw session scores for those students.
    3. Aggregate the data by week.
    4. Compute four metrics per student and write them back.
    5. Commit the transaction.

    Always returns { status = 200, records_updated = int}.
    """
    acc_rows = load_active_accelerate_records(db)
    print("1. Works")
    attend_rows = load_attendance_rows(db, [a.cti_id for a in acc_rows])
    print("2. Works")

    per_student = group_attendance_by_student(attend_rows)
    print("3. Works")
    updated = update_accelerate_records(db, acc_rows, per_student)
    print("4. Works")

    db.commit()
    print("5. Works")
    return {"status": 200, "records_updated": updated}


def load_active_accelerate_records(db: Session) -> List[Accelerate]:
    """
    Return Accelerate rows where the 'active' column is True.
    """
    return (
        db.execute(
            select(Accelerate)
            .where(Accelerate.active.is_(True))
            .options(joinedload(Accelerate.acc_owner))
        )
        .unique()
        .scalars()
        .all()
    )


def load_attendance_rows(
    db: Session,
    cti_ids: List[int],
) -> List[Tuple[int, date, float]]:
    """
    Pull raw session scores for the supplied student ids.

    Each tuple in the list is (cti_id, session_date).
    """
    if not cti_ids:
        return []

    rows = (
        db.execute(
            select(
                StudentAttendance.cti_id,
                Attendance.session_start,
            )
            .join(Attendance, Attendance.session_id == StudentAttendance.session_id)
            .where(StudentAttendance.cti_id.in_(cti_ids))
        )
        .all()
    )
    # Convert datetime to date for easier week bucketing
    return [(cid, sess.date(), score) for cid, sess, score in rows]


def group_attendance_by_student(
    attend_rows: List[Tuple[int, date, float]]
) -> Dict[int, List[Tuple[date, float]]]:
    """
    Reorganize raw rows into a dict keyed by student id.
    """
    grouped: Dict[int, List[Tuple[date, float]]] = defaultdict(list)
    for cid, sess_date, score in attend_rows:
        grouped[cid].append((sess_date, score))
    return grouped


def start_of_week(d: date) -> date:
    """Return the Monday for the calendar week that contains the date d."""
    return d - timedelta(days=d.weekday())


def compute_weekly_aggregates(
    rows: List[Tuple[date, float]],
) -> Dict[date, List[float]]:
    """
    Bucket session scores by the Monday of their week.
    """
    bucket: Dict[date, List[float]] = defaultdict(list)
    for sess_date, score in rows:
        bucket[start_of_week(sess_date)].append(score)
    return bucket


def consecutive_weeks_with_min_sessions(
    weeks: List[Tuple[date, int]],
    min_sessions: int,
) -> int:
    """
    Calculate the current streak of consecutive weeks that each meet or exceed
    'min_sessions' completed sessions.

    The list 'weeks' must be sorted newest first.
    """
    streak = 0
    expected_next = weeks[0][0] if weeks else None

    for week_start, count in weeks:
        if count < min_sessions:
            break
        if expected_next and (expected_next - week_start).days == 7:
            streak += 1
            expected_next = week_start
        elif streak == 0:
            streak = 1
            expected_next = week_start
        else:
            break
    return streak


def weighted_participation_score(
    weekly_scores: Iterable[Tuple[date, float]],
    *,
    weighted: bool = False, # default behaviour
    decay: float = 0.90,
    k: int = 1,
) -> float:
    """
    Convert per week average scores to a single 0-1 number.
    The function accepts a list of tuples (week_start, average_score) and
    returns a single number representing the average score for the weeks.
    
    The function can be used in two modes:
        - weighted: True or False
        - decay: 0.0 to 1.0

    weekly_scores: 
        - Iterable of (week_start, average_score) tuples.
    weighted:
        - If False, return the plain arithmetic mean.
        - If True, apply exponential decay so recent weeks count more.
    decay:
        - Weight multiplier applied for each week older than the most recent.
        - Example: decay 0.9 means each week is worth 90 percent of the newer one.
    k:
        - Upper cap applied to every weekly score before weighting.

    Calculation when weighted is True:
        1. Sort the weeks from oldest to newest.
        2. For each week, compute 'weeks_old' = how many 7-day steps behind the newest.
        3. Compute 'weight' = decay ** weeks_old.
        4. Add weight * min(k, score) to a running numerator.
        5. Add weight * k to a running denominator.
        6. Return numerator / denominator rounded to three decimals.

    If the list is empty the function returns 0.
    """
    pts = sorted(weekly_scores, key=lambda t: t[0])
    if not pts:
        return 0.0

    if not weighted or decay == 1.0:
        return round(sum(s for _, s in pts) / len(pts), 3)

    newest = pts[-1][0]
    num = den = 0.0
    for week_start, score in pts:
        weeks_old = (newest - week_start).days // 7
        weight = decay ** weeks_old
        num += min(k, score) * weight
        den += k * weight

    return round(num / den, 3) if den else 0.0


def metrics_for_student(
    weekly: Dict[date, List[float]],
    *,
    streak_sessions: int = 1,
) -> Dict[str, int | float]:
    """
    Compute four participation metrics for a single student.
    The function accepts a dictionary of weekly scores and returns a dictionary

    The metrics are:
        - participation_score: aggregated 0-1 score (plain mean by default)
        - sessions_attended: total number of sessions
        - participation_streak: consecutive active weeks
        - inactive_weeks: weeks since last participation
    """
    total_sessions = sum(len(v) for v in weekly.values())
    weekly_avgs = [(w, sum(v) / len(v)) for w, v in weekly.items()]

    participation_score = weighted_participation_score(
        weekly_avgs,
        weighted=False, # default behaviour
        decay=0.90, # default decay
        k=1,
    )

    weekly_counts = sorted(
        ((w, len(weekly[w])) for w in weekly),
        key=lambda t: t[0],
        reverse=True,
    )
    streak = consecutive_weeks_with_min_sessions(weekly_counts, streak_sessions)

    inactive = 0
    if weekly:
        last_week = max(weekly.keys())
        inactive = (start_of_week(date.today()) - last_week).days // 7

    return {
        "participation_score": participation_score,
        "sessions_attended": total_sessions,
        "participation_streak": streak,
        "inactive_weeks": inactive,
    }


def update_accelerate_records(
    db: Session,
    acc_rows: List[Accelerate],
    per_student: Dict[int, List[Tuple[date, float]]],
) -> int:
    """Update accelerate records with computed metrics."""

    updated = 0
    for acc in acc_rows:
        weekly = compute_weekly_aggregates(per_student.get(acc.cti_id, []))
        metrics = metrics_for_student(weekly)

        acc.participation_score = metrics["participation_score"]
        acc.sessions_attended = metrics["sessions_attended"]
        acc.participation_streak = metrics["participation_streak"]
        acc.inactive_weeks = metrics["inactive_weeks"]
        updated += 1
    return updated