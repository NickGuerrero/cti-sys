from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel

class CheckActivityRequest(BaseModel):
    target: str
    active_start: Optional[datetime] = None
    activity_thresholds: Dict[str, List[str]]

class CheckActivityResponse(BaseModel):
    status: int