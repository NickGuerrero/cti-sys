from pydantic import ValidationError
import pytest
from pymongo.database import Database as MongoDatabase
from pymongo.errors import WriteError

from src.config import ACCELERATE_FLEX_COLLECTION
from src.reports.accelerate_flex.models import AccelerateFlexBase, DeepWorkModel

class TestAccelerateFlexModel:
    @pytest.mark.parametrize("data", [
        # Required field(s) only
        {"cti_id": 100},

        # With optional nested data structure(s)
        {"cti_id": 100, "selected_deep_work": [{"day": "Friday", "time": "2-4pm", "sprint": "Spring 2024"}], "phone": "(800) 123-4567"},

        # With extra fields (should be ignored on Model construction)
        {"cti_id": 100, "selected_deep_work": [{"day": "Friday", "time": "2-4pm", "sprint": "Spring 2024"}], "phone": "(800) 123-4567", "extra_here": True},
    ])
    def test_accelerate_flex_model_valid_cases(self, data):
        AccelerateFlexBase(**data) # using Base model here rather than Model as not testing DB find result (pre-insert validation)
    
    def test_accelerate_flex_model_provides_none_values(self):
        """Test validates that a value of None is assigned to each property where that non-required, optional field is not provided
        
        Fields of default None value (unset on model creation) can be ignored and not inserted on document
        db inserts by using `collection.insert_one(model.model_dump(exclude_unset=True))`
        """
        cti_id = 100
        phone = "(800) 123-4567"
        model = AccelerateFlexBase(**{
            "cti_id": cti_id,
            "phone": phone
        })

        assert model.career_outlook == None
        assert model.selected_deep_work == None
        assert model.cti_id == cti_id

    @pytest.mark.parametrize("data", [
        # Missing required field(s)
        {},
        
        # Incorrect type
        {"cti_id": 100, "phone": 8001234567}
    ])
    def test_accelerate_flex_model_invalid_cases(self, data):
        with pytest.raises(ValidationError):
            AccelerateFlexBase(**data) # using Base model here rather than Model as not testing DB find result (pre-insert validation)

    @pytest.mark.integration
    def test_accelerate_flex_schema_rejects_invalid_insert(self, real_mongo_db: MongoDatabase):
        """Integration test validating that an accelerate_flex document will not be inserted
        if it does not follow the collection json validation schema.
        
        Relevant for inserts performed outside of API.
        """
        accelerate_flex_collection = real_mongo_db.get_collection(ACCELERATE_FLEX_COLLECTION)

        with pytest.raises(WriteError, match="Document failed validation"):
            accelerate_flex_collection.insert_one({
                # missing "cti_id": 12345,
                "selected_deep_work": DeepWorkModel(
                    day="Monday",
                    time="2pm - 4pm",
                    sprint="Spring 2024"
                ).model_dump(),
                "academic_goals": ["Bachelor's Degree", "Associate's Degree"],
                "phone": "(800) 123-4567",
                "academic_year": "Sophomore",
                "grad_year": 2027,
                "summers_left": 2,
                "cs_exp": False,
                "cs_courses": ["Data Structures", "Algorithms"],
                "math_courses": ["Calculus 1A", "Discrete Math"],
                "program_expectation": "Summer tech internship",
                "career_outlook": "Graduated and in the workforce",
                "heard_about": "Instructor/Professor",
            })
            
    @pytest.mark.integration
    def test_accelerate_flex_schema_accepts_valid_insert(self, real_mongo_db: MongoDatabase):
        """Integration test validating that an accelerate_flex document will be inserted
        if it follows the collection json validation schema.
        """
        accelerate_flex_collection = real_mongo_db.get_collection(ACCELERATE_FLEX_COLLECTION)
        prev_count = accelerate_flex_collection.count_documents({})
        cti_id = 12345

        # todo: upon a POST /api/accelerate-flex endpoint creation, this direct insert can be replaced with a TestClient call
        insert_result = accelerate_flex_collection.insert_one({
            "cti_id": cti_id,
            "selected_deep_work": DeepWorkModel(
                day="Monday",
                time="2pm - 4pm",
                sprint="Spring 2024"
            ).model_dump(),
            "academic_goals": ["Bachelor's Degree", "Associate's Degree"],
            "phone": "(800) 123-4567",
            "academic_year": "Sophomore",
            "grad_year": 2027,
            "summers_left": 2,
            "cs_exp": False,
            "cs_courses": ["Data Structures", "Algorithms"],
            "math_courses": ["Calculus 1A", "Discrete Math"],
            "program_expectation": "Summer tech internship",
            "career_outlook": "Graduated and in the workforce",
            "heard_about": "Instructor/Professor",
        })

        assert insert_result.acknowledged

        found_accelerate_flex = accelerate_flex_collection.find_one({"_id": insert_result.inserted_id})
        assert found_accelerate_flex is not None
        assert found_accelerate_flex["cti_id"] == cti_id
        assert prev_count + 1 == accelerate_flex_collection.count_documents({})
