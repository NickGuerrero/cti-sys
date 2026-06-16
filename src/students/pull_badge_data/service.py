from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pymongo import UpdateOne
from pymongo.database import Database
from pymongo.errors import BulkWriteError
from sqlalchemy.orm import Session

from src.config import BADGES_COLLECTION, STUDENT_BADGES_COLLECTION
from src.database.postgres.models import CanvasID, Student
from src.utils.rate_limiting.canvas.canvas_api import CanvasClient
from src.utils.rate_limiting.parchment_badges.parchment_api import ParchmentClient


def build_badge_upsert(badge: dict) -> Optional[UpdateOne]:
    """
    Build an UpdateOne upsert operation for a single Parchment badge.
    """
    parchment_id = badge.get("entityId")
    if not parchment_id:
        return None

    return UpdateOne(
        {"parchment_id": parchment_id},
        {"$set": {
            "parchment_id": parchment_id,
            "badge_name": badge.get("name"),
            "image_url": badge.get("image"),
            "description": badge.get("description"),
            "version": badge.get("version"),
            "last_updated": datetime.now(timezone.utc),
        }},
        upsert=True,
    )


def process_badge_batch(
    batch: List[dict],
    badges_collection,
    student_badges_collection,
    db: Session,
    canvas: CanvasClient,
) -> Dict[str, Any]:
    """
    Upsert one page of Parchment badges via bulk_write, then sync
    student badges for any of those badges that have a canvas_id linked.
    """
    errors: List[str] = []
    badges_synced = 0
    student_badges_created = 0
    student_badges_updated = 0

    operations: List[UpdateOne] = []
    parchment_ids: List[str] = []

    for badge in batch:
        op = build_badge_upsert(badge)
        if op is None:
            continue
        operations.append(op)
        parchment_ids.append(badge["entityId"])

    if operations:
        try:
            result = badges_collection.bulk_write(operations, ordered=False)
            badges_synced += result.upserted_count + result.matched_count
        except BulkWriteError as bwe:
            # Some operations in the batch may have succeeded; only report failures.
            write_errors = bwe.details.get("writeErrors", [])
            failed_indexes = {err["index"] for err in write_errors}
            badges_synced += len(operations) - len(failed_indexes)
            for err in write_errors:
                failed_parchment_id = parchment_ids[err["index"]]
                errors.append(f"Error processing badge {failed_parchment_id}: {err.get('errmsg')}")

    stored_badges = {
        doc["parchment_id"]: doc
        for doc in badges_collection.find({"parchment_id": {"$in": parchment_ids}})
    }

    for parchment_id in parchment_ids:
        try:
            existing_badge = stored_badges.get(parchment_id)
            canvas_id = existing_badge.get("canvas_id") if existing_badge else None

            if canvas_id:
                created, updated = sync_student_badges(
                    canvas_id=canvas_id,
                    badge=existing_badge,
                    student_badges_collection=student_badges_collection,
                    db=db,
                    canvas=canvas,
                )
                student_badges_created += created
                student_badges_updated += updated
        except Exception as e:
            errors.append(f"Error processing badge {parchment_id}: {str(e)}")

    return {
        "badges_synced": badges_synced,
        "student_badges_created": student_badges_created,
        "student_badges_updated": student_badges_updated,
        "errors": errors,
    }


def pull_badge_data(
    mongo: Database,
    db: Session,
) -> Dict[str, Any]:
    """
    Stream badge classes from Parchment and sync into MongoDB, one page at a time.
    For each badge, if it has a linked canvas_id, also sync student badges for enrolled students.
    """
    badges_collection = mongo.get_collection(BADGES_COLLECTION)
    student_badges_collection = mongo.get_collection(STUDENT_BADGES_COLLECTION)

    parchment = ParchmentClient()
    canvas = CanvasClient()

    errors: List[str] = []
    total_badges_from_parchment = 0
    badges_synced = 0
    student_badges_created = 0
    student_badges_updated = 0

    for batch in parchment.stream_badges():
        total_badges_from_parchment += len(batch)

        batch_result = process_badge_batch(
            batch=batch,
            badges_collection=badges_collection,
            student_badges_collection=student_badges_collection,
            db=db,
            canvas=canvas,
        )

        badges_synced += batch_result["badges_synced"]
        student_badges_created += batch_result["student_badges_created"]
        student_badges_updated += batch_result["student_badges_updated"]
        errors.extend(batch_result["errors"])

    return {
        "status": 200,
        "total_badges_from_parchment": total_badges_from_parchment,
        "badges_synced": badges_synced,
        "student_badges_created": student_badges_created,
        "student_badges_updated": student_badges_updated,
        "errors": errors,
    }


def lookup_cti_id(canvas_user_id: int, db: Session) -> Optional[int]:
    """Look up cti_id from canvas_ids table by Canvas user ID."""
    record = db.query(CanvasID).filter(CanvasID.canvas_id == canvas_user_id).first()
    return record.cti_id if record else None


def lookup_student_name(cti_id: int, db: Session) -> Optional[str]:
    """Look up student full name from students table by cti_id."""
    student = db.query(Student).filter(Student.cti_id == cti_id).first()
    if not student:
        return None
    return f"{student.fname} {student.lname}"


def sync_student_badges(
    *,
    canvas_id: int,
    badge: dict,
    student_badges_collection,
    db: Session,
    canvas: CanvasClient,
) -> Tuple[int, int]:
    """
    For a given Canvas course linked to a badge, create or update StudentBadge records
    for all enrolled students with their completion percentage.
    """
    enrollments = canvas.get_course_enrollments(canvas_id)
    progress_map = canvas.get_bulk_user_progress(canvas_id)

    # create a snapshot of badge info to store in each StudentBadge record
    badge_info_snapshot = {
        "badge_name": badge.get("badge_name"),
        "parchment_id": badge.get("parchment_id"),
        "image_url": badge.get("image_url"),
        "version": badge.get("version"),
    }

    created = 0
    updated = 0

    for enrollment in enrollments:
        canvas_user_id = enrollment.get("user_id")
        if not canvas_user_id:
            continue

        # cross-reference Canvas user ID with our cti_id in Postgres
        cti_id = lookup_cti_id(canvas_user_id, db)
        if not cti_id:
            continue

        completion_percentage = progress_map.get(canvas_user_id)

        existing = student_badges_collection.find_one(
            {"cti_id": cti_id, "parchment_id": badge.get("parchment_id")}
        )

        if existing:
            # update completion percentage only
            student_badges_collection.update_one(
                {"cti_id": cti_id, "parchment_id": badge.get("parchment_id")},
                {"$set": {"completion_percentage": completion_percentage}},
            )
            updated += 1
        else:
            student_badges_collection.insert_one(
                {
                    "cti_id": cti_id,
                    "student_name": lookup_student_name(cti_id, db),
                    "parchment_id": badge.get("parchment_id"),
                    "badge_info": badge_info_snapshot,
                    "completion_percentage": completion_percentage,
                    "date_awarded": None,
                    "artifacts": [],
                }
            )
            created += 1

    return created, updated