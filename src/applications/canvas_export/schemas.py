from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

class SISImportObject(BaseModel):
    """
    Canvas SIS Import data response object.

    url:POST|/api/v1/accounts/:account_id/sis_imports
    https://canvas.instructure.com/doc/api/sis_imports.html#method.sis_imports_api.create
    """
    id: int
    created_at: datetime
    ended_at: Optional[datetime]  = Field(default=None)
    updated_at: Optional[datetime]  = Field(default=None)
    workflow_state: str
    data: Optional[Any]  = Field(default=None)
    statistics: Optional[Any]  = Field(default=None)
    progress: int
    errors_attachment: Optional[Any]  = Field(default=None)
    user: Optional[Any]  = Field(default=None)
    processing_warnings: Optional[list] = Field(default=[])
    processing_errors: list = Field(default=[])
    batch_mode: Optional[bool] = Field(default=None)
    batch_mode_term_id: Optional[int] = Field(default=None)
    multi_term_batch_mode: Optional[bool] = Field(default=False)
    skips_deletes: Optional[bool] = Field(default=False)
    override_sis_stickiness: Optional[bool] = Field(default=False)
    add_sis_stickiness: Optional[bool] = Field(default=False)
    diffing_data_set_identifier: Optional[str]  = Field(default=None)
    diffed_against_import_id: Optional[int]  = Field(default=None)
    csv_attachments: list = Field(default=[])

class SISUserObject(BaseModel):
    """
    Canvas User response object.
    """
    id: int = Field(description="Canvas ID of User")
    name: str = Field(description="Full name of User")
    created_at: datetime = Field(description="When the user was instantiated within Canvas")
    sortable_name: str
    last_name: Optional[str] = Field(default=None)
    first_name: Optional[str] = Field(default=None)
    short_name: Optional[str] = Field(default=None)
    # NOTE sis_user_id optional to account for None cases in production (consider manual fix)
    sis_user_id: Optional[str] = Field(description="SIS User ID, defaulted as login email")
    sis_import_id: Optional[int] = Field(default=None)
    integration_id: Optional[str] = Field(default=None)
    login_id: Optional[str] = Field(default=None)
    avatar_url: Optional[str] = Field(default=None)
    avatar_state: Optional[str] = Field(default=None)
    enrollments: Optional[list] = Field(default=None)
    email: Optional[str] = Field(default=None)
    locale: Optional[str] = Field(default=None)
    last_login: Optional[datetime] = Field(default=None)
    time_zone: Optional[str] = Field(default=None)
    bio: Optional[str] = Field(default=None)
    pronouns: Optional[str] = Field(default=None)

class CanvasExportResponse(BaseModel):
    success: bool
    applicants_enrolled: int
    users_import_id: int
    enrollments_import_id: int
    batch_date: datetime
    elapsed_time: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "applicants_enrolled": 9,
                    "users_import_id": 126,
                    "enrollments_import_id": 127,
                    "batch_date": "2025-04-25T06:28:12.770Z",
                    "elapsed_time": "21.53s"
                }
            ]
        }
    }
