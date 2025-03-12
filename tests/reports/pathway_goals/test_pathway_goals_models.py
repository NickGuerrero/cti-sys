from pydantic import ValidationError
import pytest
from pymongo.database import Database as MongoDatabase
from pymongo.errors import WriteError

from src.config import PATHWAY_GOALS_COLLECTION
from src.reports.pathway_goals.models import PathwayGoalBase

class TestPathwayGoalModel:
    @pytest.mark.parametrize("data", [
        # Required field(s) only
        {"pathway_goal": "Summer Tech Internship 2025"},

        # With optional field(s)
        {"pathway_goal": "Summer Tech Internship 2025", "course_req": ["101A", "202"]},
    ])
    def test_pathway_goal_model_valid_cases(self, data):
        PathwayGoalBase(**data) # using Base model here rather than Model as not testing DB find result (pre-insert validation)
    
    def test_pathway_goal_model_provides_none_values(self):
        """Test validates that a value of None is assigned to each property where that non-required, optional field is not provided
        
        Fields of default None value (unset on model creation) can be ignored and not inserted on document
        db inserts by using `collection.insert_one(model.model_dump(exclude_unset=True))`
        """
        pathway_goal = "Summer Tech Internship 2025"
        model = PathwayGoalBase(**{
            "pathway_goal": pathway_goal,
        })

        assert model.course_req == None
        assert model.pathway_desc == None
        assert model.pathway_goal == pathway_goal

    @pytest.mark.parametrize("data", [
        # Missing required field(s)
        {},
        
        # Extra field provided
        {"pathway_goal": "Summer Tech Internship 2025", "not_meant_to_be_here": "here"},

        # Incorrect type
        {"pathway_goal": "Summer Tech Internship 2025", "pathway_desc": ["should not be list"]}
    ])
    def test_pathway_goal_model_invalid_cases(self, data):
        with pytest.raises(ValidationError):
            PathwayGoalBase(**data) # using Base model here rather than Model as not testing DB find result (pre-insert validation)

    @pytest.mark.integration
    def test_pathway_goals_schema_rejects_invalid_insert(self, real_mongo_db: MongoDatabase):
        """Integration test validating that a pathway_goals document will not be inserted
        if it does not follow the collection json validation schema.
        
        Relevant for inserts performed outside of API.
        """
        pathway_goals_collection = real_mongo_db.get_collection(PATHWAY_GOALS_COLLECTION)

        with pytest.raises(WriteError, match="Document failed validation"):
            pathway_goals_collection.insert_one({
                "pathway_goal": "Summer Tech Internship 2025",
                "pathway_desc": "Obtain a summer tech internship for 2025",
                "course_req": "101A" # needs to be an array of strings
            })

    @pytest.mark.integration
    def test_pathway_goals_schema_accepts_valid_insert(self, real_mongo_db: MongoDatabase):
        """Integration test validating that a pathway_goals document will be inserted
        if it follows the collection json validation schema.
        """
        pathway_goals_collection = real_mongo_db.get_collection(PATHWAY_GOALS_COLLECTION)
        prev_count = pathway_goals_collection.count_documents({})
        pathway_goal = "Summer Tech Internship 2025"
        pathway_desc = "Obtain a summer tech internship for 2025"
        course_req = ["101A", "202A"]

        # todo: upon a POST /api/pathway-goals endpoint creation, this direct insert can be replaced with a TestClient call
        insert_result = pathway_goals_collection.insert_one({
            "pathway_goal": pathway_goal,
            "pathway_desc": pathway_desc,
            "course_req": course_req
        })

        assert insert_result.acknowledged

        found_pathway_goal = pathway_goals_collection.find_one({"_id": insert_result.inserted_id})
        assert found_pathway_goal is not None
        assert found_pathway_goal["pathway_goal"] == pathway_goal
        assert prev_count + 1 == pathway_goals_collection.count_documents({})
