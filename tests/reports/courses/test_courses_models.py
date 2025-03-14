from pydantic import ValidationError
import pytest
from pymongo.database import Database as MongoDatabase
from pymongo.errors import WriteError

from src.config import COURSES_COLLECTION
from src.reports.courses.models import CourseBase

class TestCoursesModels:
    @pytest.mark.parametrize("data", [
        # Required field(s) only
        {"course_id": "101"},

        # With optional field(s)
        {"course_id": "101", "canvas_id": 1234, "title": "Introduction to Problem Solving"},
    ])
    def test_course_model_valid_cases(self, data):
        CourseBase(**data) # using Base model here rather than Model as not testing DB find result (pre-insert validation)
    
    def test_course_model_provides_none_values(self):
        """Test validates that a value of None is assigned to each property where that non-required, optional field is not provided
        
        Fields of default None value (unset on model creation) can be ignored and not inserted on document
        db inserts by using `collection.insert_one(model.model_dump(exclude_unset=True))`
        """
        course_id = "101"
        model = CourseBase(**{
            "course_id": course_id,
        })

        assert model.canvas_id == None
        assert model.milestones == None
        assert model.version == None
        assert model.course_id == course_id

    @pytest.mark.parametrize("data", [
        # Missing required field(s)
        {},
        
        # Extra field provided
        {"course_id": "101", "should not be here": "here"},

        # Incorrect type
        {"course_id": "101", "canvas_id": "z12345"},
    ])
    def test_course_model_invalid_cases(self, data):
        with pytest.raises(ValidationError):
            CourseBase(**data) # using Base model here rather than Model as not testing DB find result (pre-insert validation)

    @pytest.mark.integration
    def test_courses_schema_rejects_invalid_insert(self, real_mongo_db: MongoDatabase):
        """Integration test validating that a courses document will not be inserted
        if it does not follow the collection json validation schema.
        
        Relevant for inserts performed outside of API.
        """
        courses_collection = real_mongo_db.get_collection(COURSES_COLLECTION)

        with pytest.raises(WriteError, match="Document failed validation"):
            courses_collection.insert_one({
                "course_id": "101",
                "canvas_id": "12345", # if provided, needs to be integer value
                "title": "Introduction to Problem Solving",
                "milestones": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
                "version": "1.0.0"
            })

    @pytest.mark.integration
    def test_courses_schema_accepts_valid_insert(self, real_mongo_db: MongoDatabase):
        """Integration test validating that a courses document will be inserted
        if it follows the collection json validation schema.
        """
        courses_collection = real_mongo_db.get_collection(COURSES_COLLECTION)
        prev_count = courses_collection.count_documents({})

        course_id = "101"
        canvas_id = 12345
        title = "Introduction to Problem Solving"
        milestones = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        version = "1.0.0"

        # todo: upon a POST /api/courses endpoint creation, this direct insert can be replaced with a TestClient call
        insert_result = courses_collection.insert_one({
            "course_id": course_id,
            "canvas_id": canvas_id,
            "title": title,
            "milestones": milestones,
            "version": version
        })

        assert insert_result.acknowledged

        found_course = courses_collection.find_one({"_id": insert_result.inserted_id})
        assert found_course is not None
        assert found_course["course_id"] == course_id
        assert prev_count + 1 == courses_collection.count_documents({})
