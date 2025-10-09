from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive = False, # Make environment variable names case-insensitive TODO: Not sure if we actually want this
        env_file = ".env", # Load environment variables from .env file, if available
        extra = "ignore", # Ignore any extra fields not defined in the model
    )

    # All env vars should be declared manually, never assume automatic behavior
    # Apart from constants or required env vars, you should verify the values exist at runtime
    app_env: str = Field(validation_alias="APP_ENV", pattern=r'^(development|production)$', default="development")
    # TODO: Convert this into a general purpose API key
    cti_sys_admin_key: Optional[str] = Field(default=None, validation_alias="CTI_SYS_ADMIN_KEY")

    # Database Connection Strings, required for Database operations
    # TODO: Validate these as connection strings, with user, pass, db, and host
    cti_mongo_url: Optional[str] = Field(validation_alias="CTI_MONGO_URL", default=None)
    cti_postgres_url: Optional[str] = Field(validation_alias="CTI_POSTGRES_URL", default=None)

    # Canvas Variables, only required for Canvas specific-operations
    # NOTE: SIS ID's are needed for SIS operations, must be manually defined ahead of time
    # TODO: Rename CTI_ACCESS_TOKEN to CTI_CANVAS_TOKEN, improve clarity on token purpose and differentiate from server token
    cti_access_token: Optional[str] = Field(validation_alias="CTI_ACCESS_TOKEN", default=None)
    # The reason the actual env name is flipped is to align it with the other course id, COURSE_ID_101
    unterview_course_id: Optional[int] = Field(validation_alias="COURSE_ID_UNTERVIEW", default=None)
    unterview_sis_course_id: Optional[str] = Field(validation_alias="UNTERVIEW_SIS_COURSE_ID", default=None)
    current_unterview_sis_section_id: Optional[str] = Field(validation_alias="CUR_UNTERVIEW_SIS_SECTION_ID", default=None)
    current_unterview_section_id: Optional[int] = Field(validation_alias="CUR_UNTERVIEW_SECTION_ID", default=None)
    commitment_quiz_id: Optional[int] = Field(validation_alias="COMMITMENT_QUIZ_ID", default=None)
    course_id_101: Optional[int] = Field(validation_alias="COURSE_ID_101", default=None) # currenlty unused

    # SendGrid Variables, only required for email delivery operations
    sendgrid_api_key: Optional[str] = Field(validation_alias="SENDGRID_API_KEY", default=None)
    sendgrid_sender: Optional[str] = Field(validation_alias="SENDGRID_SENDER", default=None)

    # Google Cloud Authorization, only required for Google Sheet integrations
    roster_sheet_key: Optional[str] = Field(validation_alias="ROSTER_SHEET_KEY", default=None)
    test_sheet_key: Optional[str] = Field(validation_alias="TEST_SHEET_KEY", default=None)
    gs_509_cert_url: Optional[str] = Field(validation_alias="GS_509_CERT_URL", default=None)
    gs_client_id: Optional[str] = Field(validation_alias="GS_CLIENT_ID", default=None)
    gs_client_email: Optional[str] = Field(validation_alias="GS_CLIENT_EMAIL", default=None)
    gs_private_key: Optional[str] = Field(validation_alias="GS_PRIVATE_KEY", default=None)
    gs_private_key_id: Optional[str] = Field(validation_alias="GS_PRIVATE_KEY_ID", default=None)
    gs_project_id: Optional[str] = Field(validation_alias="GS_PROJECT_ID", default=None)

    # Application Constants
    canvas_api_url: str = "https://cti-courses.test.instructure.com"
    canvas_api_test_url: str = "https://cti-courses.test.instructure.com"
    sa_whitelist: str = "SA Whitelist"

settings = Settings()

# TODO: Move these into the settings object properly
# MongoDB
MONGO_DATABASE_NAME = "cti_mongo_db"
APPLICATIONS_COLLECTION = "applications"
ACCELERATE_FLEX_COLLECTION = "accelerate_flex"
PATHWAY_GOALS_COLLECTION = "pathway_goals"
COURSES_COLLECTION = "courses"
