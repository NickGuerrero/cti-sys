from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel

class MasterRosterCreateResponse(BaseModel):
    status: int
    message: str

class QuizSubmissionWorkflowState(Enum):
    UNTAKEN = "untaken"
    PENDING_REVIEW = "pending_review"
    COMPLETE = "complete"
    SETTINGS_ONLY = "settings_only"
    PREVIEW = "preview"

class QuizSubmission(BaseModel):
    """
    Canvas Quiz Submission response object.

    url:GET|/api/v1/courses/:course_id/quizzes/:quiz_id/submission 
    https://canvas.instructure.com/doc/api/quiz_submissions.html
    """
    id: int
    quiz_id: int
    user_id: int
    submission_id: Optional[int]
    started_at: datetime
    finished_at: datetime
    end_at: Optional[datetime]
    attempt: int
    extra_attempts: Optional[int]
    extra_time: Optional[int]
    manually_unlocked: Optional[bool]
    time_spent: int
    score: float
    score_before_regrade: Optional[float]
    kept_score: float
    fudge_points: Optional[float]
    has_seen_results: bool
    workflow_state: QuizSubmissionWorkflowState
    overdue_and_needs_submission: bool
