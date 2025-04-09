from datetime import datetime
from pydantic import BaseModel

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
    id: int
    name: str
    sortable_name: str
    last_name: str
    first_name: str
    short_name: str
    sis_user_id: str
    sis_import_id: int
    integration_id: str
    login_id: str
    avatar_url: str
    avatar_state: str # todo: enum
    enrollments: None
    email: str
    locale: str
    last_login: datetime
    time_zone: str
    bio: str
    pronouns: str
