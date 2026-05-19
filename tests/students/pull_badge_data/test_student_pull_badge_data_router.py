from datetime import datetime, timezone
from unittest.mock import MagicMock
from src.config import BADGES_COLLECTION, STUDENT_BADGES_COLLECTION
import src.students.pull_badge_data.service as svc


class TestPullBadgeData:

    def make_parchment_badge(
        self,
        entity_id="ajuBF97BRjG_dd7xmv5zmg",
        name="101 Completion",
        image="https://api.badgr.io/public/badges/ajuBF97BRjG_dd7xmv5zmg/image",
        description="101 Completion",
    ):
        """Return a minimal Parchment badge dict matching the API envelope result shape."""
        return {
            "entityId": entity_id,
            "name": name,
            "image": image,
            "description": description,
        }

    def make_canvas_enrollment(self, user_id=4858, name="Jose Campos Rodriguez"):
        """Return a minimal Canvas enrollment dict."""
        return {
            "user_id": user_id,
            "user": {"name": name},
        }

    def mock_parchment(self, monkeypatch, badges):
        """Patch ParchmentClient to return a fixed list of badges."""
        monkeypatch.setattr(
            "src.students.pull_badge_data.service.ParchmentClient",
            MagicMock(return_value=MagicMock(
                get_all_badges=MagicMock(return_value=badges)
            ))
        )

    def mock_canvas(self, monkeypatch, enrollments=None, progress_map=None):
        """Patch CanvasClient to return fixed enrollments and progress data."""
        monkeypatch.setattr(
            "src.students.pull_badge_data.service.CanvasClient",
            MagicMock(return_value=MagicMock(
                get_course_enrollments=MagicMock(return_value=enrollments or []),
                get_bulk_user_progress=MagicMock(return_value=progress_map or {}),
            ))
        )

    def test_badges_synced_from_parchment(self, client, mock_mongo_db, mock_postgresql_db, monkeypatch):
        """All badges returned by Parchment are upserted into the badges collection."""
        badge = self.make_parchment_badge()
        self.mock_parchment(monkeypatch, [badge])
        self.mock_canvas(monkeypatch)

        res = client.post("/api/students/pull-badge-data")
        assert res.status_code == 200

        data = res.json()
        assert data["total_badges_from_parchment"] == 1
        assert data["badges_synced"] == 1
        assert data["errors"] == []

        stored = mock_mongo_db[BADGES_COLLECTION].find_one(
            {"parchment_id": "ajuBF97BRjG_dd7xmv5zmg"}
        )
        assert stored is not None
        assert stored["badge_name"] == "101 Completion"
        assert stored["image_url"] == "https://api.badgr.io/public/badges/ajuBF97BRjG_dd7xmv5zmg/image"
        assert stored["description"] == "101 Completion"

    def test_canvas_id_not_overwritten_by_sync(self, client, mock_mongo_db, mock_postgresql_db, monkeypatch):
        """canvas_id manually set on a badge document is never overwritten by sync."""
        mock_mongo_db[BADGES_COLLECTION].insert_one({
            "parchment_id": "ajuBF97BRjG_dd7xmv5zmg",
            "badge_name": "Old Name",
            "image_url": "https://old.url/image",
            "description": "Old",
            "canvas_id": 170,
            "last_updated": datetime.now(timezone.utc),
        })

        badge = self.make_parchment_badge(name="New Name", image="https://new.url/image")
        self.mock_parchment(monkeypatch, [badge])
        self.mock_canvas(monkeypatch)
        monkeypatch.setattr(svc, "lookup_cti_id", lambda canvas_user_id, db: None)

        res = client.post("/api/students/pull-badge-data")
        assert res.status_code == 200

        stored = mock_mongo_db[BADGES_COLLECTION].find_one(
            {"parchment_id": "ajuBF97BRjG_dd7xmv5zmg"}
        )
        assert stored["badge_name"] == "New Name"
        assert stored["image_url"] == "https://new.url/image"
        assert stored["canvas_id"] == 170

    def test_badge_with_no_entity_id_is_skipped(self, client, mock_mongo_db, mock_postgresql_db, monkeypatch):
        """A badge with no entityId from Parchment is skipped cleanly."""
        bad_badge = {"name": "No ID Badge", "image": "https://img.url/badge.png"}
        self.mock_parchment(monkeypatch, [bad_badge])
        self.mock_canvas(monkeypatch)

        res = client.post("/api/students/pull-badge-data")
        assert res.status_code == 200
        assert res.json()["badges_synced"] == 0
        assert mock_mongo_db[BADGES_COLLECTION].count_documents({}) == 0

    def test_multiple_badges_synced(self, client, mock_mongo_db, mock_postgresql_db, monkeypatch):
        """Multiple badges from Parchment are all upserted correctly."""
        badges = [
            self.make_parchment_badge(entity_id="id_1", name="101 Completion"),
            self.make_parchment_badge(entity_id="id_2", name="201 Completion"),
            self.make_parchment_badge(entity_id="id_3", name="301 Completion"),
        ]
        self.mock_parchment(monkeypatch, badges)
        self.mock_canvas(monkeypatch)

        res = client.post("/api/students/pull-badge-data")
        assert res.status_code == 200
        assert res.json()["total_badges_from_parchment"] == 3
        assert res.json()["badges_synced"] == 3
        assert mock_mongo_db[BADGES_COLLECTION].count_documents({}) == 3

    def test_student_badge_created_for_enrolled_student(self, client, mock_mongo_db, mock_postgresql_db, monkeypatch):
        """A StudentBadge record is created for a student enrolled in a linked Canvas course."""
        mock_mongo_db[BADGES_COLLECTION].insert_one({
            "parchment_id": "ajuBF97BRjG_dd7xmv5zmg",
            "badge_name": "101 Completion",
            "image_url": "https://api.badgr.io/public/badges/ajuBF97BRjG_dd7xmv5zmg/image",
            "description": "101 Completion",
            "canvas_id": 170,
            "last_updated": datetime.now(timezone.utc),
        })

        badge = self.make_parchment_badge()
        enrollment = self.make_canvas_enrollment(user_id=4858, name="Jose Campos Rodriguez")

        self.mock_parchment(monkeypatch, [badge])
        self.mock_canvas(
            monkeypatch,
            enrollments=[enrollment],
            progress_map={4858: 0.2245},
        )
        monkeypatch.setattr(svc, "lookup_cti_id", lambda canvas_user_id, db: 4337)
        monkeypatch.setattr(svc, "lookup_student_name", lambda cti_id, db: "Jose Campos Rodriguez")

        res = client.post("/api/students/pull-badge-data")
        assert res.status_code == 200
        assert res.json()["student_badges_created"] == 1
        assert res.json()["student_badges_updated"] == 0

        stored = mock_mongo_db[STUDENT_BADGES_COLLECTION].find_one({"cti_id": 4337})
        assert stored is not None
        assert stored["student_name"] == "Jose Campos Rodriguez"
        assert stored["parchment_id"] == "ajuBF97BRjG_dd7xmv5zmg"
        assert stored["completion_percentage"] == 0.2245
        assert stored["date_awarded"] is None
        assert stored["artifacts"] == []

    def test_student_badge_updated_not_duplicated(self, client, mock_mongo_db, mock_postgresql_db, monkeypatch):
        """An existing StudentBadge is updated on re-run, not duplicated."""
        mock_mongo_db[BADGES_COLLECTION].insert_one({
            "parchment_id": "ajuBF97BRjG_dd7xmv5zmg",
            "badge_name": "101 Completion",
            "image_url": "https://api.badgr.io/public/badges/ajuBF97BRjG_dd7xmv5zmg/image",
            "description": "101 Completion",
            "canvas_id": 170,
            "last_updated": datetime.now(timezone.utc),
        })
        mock_mongo_db[STUDENT_BADGES_COLLECTION].insert_one({
            "cti_id": 4337,
            "parchment_id": "ajuBF97BRjG_dd7xmv5zmg",
            "student_name": "Jose Campos Rodriguez",
            "badge_info": {},
            "completion_percentage": 0.1,
            "date_awarded": None,
            "artifacts": [],
        })

        badge = self.make_parchment_badge()
        enrollment = self.make_canvas_enrollment(user_id=4858)

        self.mock_parchment(monkeypatch, [badge])
        self.mock_canvas(
            monkeypatch,
            enrollments=[enrollment],
            progress_map={4858: 0.2245},
        )
        monkeypatch.setattr(svc, "lookup_cti_id", lambda canvas_user_id, db: 4337)
        monkeypatch.setattr(svc, "lookup_student_name", lambda cti_id, db: "Jose Campos Rodriguez")

        res = client.post("/api/students/pull-badge-data")
        assert res.status_code == 200
        assert res.json()["student_badges_created"] == 0
        assert res.json()["student_badges_updated"] == 1

        count = mock_mongo_db[STUDENT_BADGES_COLLECTION].count_documents(
            {"cti_id": 4337, "parchment_id": "ajuBF97BRjG_dd7xmv5zmg"}
        )
        assert count == 1

        stored = mock_mongo_db[STUDENT_BADGES_COLLECTION].find_one({"cti_id": 4337})
        assert stored["completion_percentage"] == 0.2245

    def test_student_not_in_system_is_skipped(self, client, mock_mongo_db, mock_postgresql_db, monkeypatch):
        """A student enrolled in Canvas but not in our system is skipped cleanly."""
        mock_mongo_db[BADGES_COLLECTION].insert_one({
            "parchment_id": "ajuBF97BRjG_dd7xmv5zmg",
            "badge_name": "101 Completion",
            "image_url": "https://api.badgr.io/public/badges/ajuBF97BRjG_dd7xmv5zmg/image",
            "description": "101 Completion",
            "canvas_id": 170,
            "last_updated": datetime.now(timezone.utc),
        })

        badge = self.make_parchment_badge()
        enrollment = self.make_canvas_enrollment(user_id=9999)

        self.mock_parchment(monkeypatch, [badge])
        self.mock_canvas(
            monkeypatch,
            enrollments=[enrollment],
            progress_map={9999: 0.5},
        )
        monkeypatch.setattr(svc, "lookup_cti_id", lambda canvas_user_id, db: None)

        res = client.post("/api/students/pull-badge-data")
        assert res.status_code == 200
        assert res.json()["student_badges_created"] == 0
        assert mock_mongo_db[STUDENT_BADGES_COLLECTION].count_documents({}) == 0

    def test_date_awarded_not_overwritten_on_update(self, client, mock_mongo_db, mock_postgresql_db, monkeypatch):
        """date_awarded on an existing StudentBadge is never overwritten by a sync."""
        awarded_date = datetime(2025, 6, 1)

        mock_mongo_db[BADGES_COLLECTION].insert_one({
            "parchment_id": "ajuBF97BRjG_dd7xmv5zmg",
            "badge_name": "101 Completion",
            "image_url": "https://api.badgr.io/public/badges/ajuBF97BRjG_dd7xmv5zmg/image",
            "description": "101 Completion",
            "canvas_id": 170,
            "last_updated": datetime.now(timezone.utc),
        })
        mock_mongo_db[STUDENT_BADGES_COLLECTION].insert_one({
            "cti_id": 4337,
            "parchment_id": "ajuBF97BRjG_dd7xmv5zmg",
            "student_name": "Jose Campos Rodriguez",
            "badge_info": {},
            "completion_percentage": 1.0,
            "date_awarded": awarded_date,
            "artifacts": [],
        })

        badge = self.make_parchment_badge()
        enrollment = self.make_canvas_enrollment(user_id=4858)

        self.mock_parchment(monkeypatch, [badge])
        self.mock_canvas(
            monkeypatch,
            enrollments=[enrollment],
            progress_map={4858: 1.0},
        )
        monkeypatch.setattr(svc, "lookup_cti_id", lambda canvas_user_id, db: 4337)
        monkeypatch.setattr(svc, "lookup_student_name", lambda cti_id, db: "Jose Campos Rodriguez")

        res = client.post("/api/students/pull-badge-data")
        assert res.status_code == 200

        stored = mock_mongo_db[STUDENT_BADGES_COLLECTION].find_one({"cti_id": 4337})
        assert stored["date_awarded"] == awarded_date

    def test_badge_without_canvas_id_skips_student_sync(self, client, mock_mongo_db, mock_postgresql_db, monkeypatch):
        """A badge with no canvas_id linked does not trigger student badge sync."""
        badge = self.make_parchment_badge()
        self.mock_parchment(monkeypatch, [badge])
        self.mock_canvas(monkeypatch)

        res = client.post("/api/students/pull-badge-data")
        assert res.status_code == 200
        assert res.json()["student_badges_created"] == 0
        assert mock_mongo_db[STUDENT_BADGES_COLLECTION].count_documents({}) == 0

    def test_error_on_one_badge_does_not_stop_others(self, client, mock_mongo_db, mock_postgresql_db, monkeypatch):
        """An error processing one badge does not prevent other badges from processing."""
        badges = [
            self.make_parchment_badge(entity_id="bad_id", name="Bad Badge"),
            self.make_parchment_badge(entity_id="good_id", name="Good Badge"),
        ]
        self.mock_parchment(monkeypatch, badges)
        self.mock_canvas(monkeypatch)

        original_update = mock_mongo_db[BADGES_COLLECTION].update_one
        def patched_update(filter_doc, *args, **kwargs):
            if filter_doc.get("parchment_id") == "bad_id":
                raise Exception("Simulated DB error")
            return original_update(filter_doc, *args, **kwargs)
        mock_mongo_db[BADGES_COLLECTION].update_one = patched_update

        res = client.post("/api/students/pull-badge-data")
        assert res.status_code == 200

        data = res.json()
        assert data["badges_synced"] == 1
        assert len(data["errors"]) == 1
        assert "bad_id" in data["errors"][0]

    def test_completion_percentage_stored_correctly(self, client, mock_mongo_db, mock_postgresql_db, monkeypatch):
        """Completion percentage from Canvas bulk progress is stored accurately."""
        mock_mongo_db[BADGES_COLLECTION].insert_one({
            "parchment_id": "ajuBF97BRjG_dd7xmv5zmg",
            "badge_name": "101 Completion",
            "image_url": "https://api.badgr.io/public/badges/ajuBF97BRjG_dd7xmv5zmg/image",
            "description": "101 Completion",
            "canvas_id": 170,
            "last_updated": datetime.now(timezone.utc),
        })

        badge = self.make_parchment_badge()
        enrollment = self.make_canvas_enrollment(user_id=4858)

        self.mock_parchment(monkeypatch, [badge])
        self.mock_canvas(
            monkeypatch,
            enrollments=[enrollment],
            progress_map={4858: 0.3265},
        )
        monkeypatch.setattr(svc, "lookup_cti_id", lambda canvas_user_id, db: 4337)
        monkeypatch.setattr(svc, "lookup_student_name", lambda cti_id, db: "Aung Nanda Oo")

        res = client.post("/api/students/pull-badge-data")
        assert res.status_code == 200

        stored = mock_mongo_db[STUDENT_BADGES_COLLECTION].find_one({"cti_id": 4337})
        assert stored["completion_percentage"] == 0.3265
