from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class SISImportObject(BaseModel):
    """
    Canvas SIS Import data response object.

    url:POST|/api/v1/accounts/:account_id/sis_imports
    https://canvas.instructure.com/doc/api/sis_imports.html#method.sis_imports_api.create
    """
    id: int
    created_at: datetime
    ended_at: datetime
    updated_at: datetime
    workflow_state: str # todo: enum
    data: None
    statistics: None
    progress: int
    errors_attachment: None
    user: None
    processing_warnings: list
    processing_errors: list
    batch_mode: bool
    batch_mode_term_id: int
    multi_term_batch_mode: bool
    skips_deletes: bool
    override_sis_stickiness: bool
    add_sis_stickiness: bool
    diffing_data_set_identifier: str
    diffed_against_import_id: int
    csv_attachments: list

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
    sis_user_id: str = Field(description="SIS User ID, defaulted as login email")
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
    # todo: define with known call responses
    pass