from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from src.models import PyObjectId

# mongo models...
class PathwayGoalBase(BaseModel):
    pathway_goal: str = Field(description="Name for the pathway goal")
    pathway_desc: Optional[str] = Field(default=None, description="Description of the pathway goal")
    course_req: Optional[List[str]] = Field(default=None, description="Courses required for the pathway goal")

    model_config = ConfigDict(extra="forbid")

class PathwayGoalModel(PathwayGoalBase):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
