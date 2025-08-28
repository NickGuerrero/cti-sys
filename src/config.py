from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    app_env: str = "development"
    unterview_course_id: int = 161
    unterview_sis_course_id: str = "S161"
    current_unterview_sis_section_id: str = "S194" # NOTE had to manually define this in Canvas
    current_unterview_section_id: int = 194
    canvas_api_url: str = "https://cti-courses.test.instructure.com"
    canvas_api_test_url: str = "https://cti-courses.test.instructure.com"

    # SA's Sheet URL for allowed emails and form submissions password
    allowed_sas_sheet_url: Optional[str] = Field(default=None, validation_alias="ALLOWED_SAS_SHEET_URL")
    attendance_password: Optional[str] = Field(default=None, validation_alias="ATTENDANCE_PASSWORD")
    attendance_api_key: Optional[str] = Field(default=None, validation_alias="ATTENDANCE_API_KEY")

    model_config = SettingsConfigDict(
        case_sensitive = False, # Make environment variable names case-insensitive
        env_file = ".env", # Load environment variables from .env file
        extra = "ignore", # Ignore any extra fields not defined in the model
    )

settings = Settings()

# MongoDB
MONGO_DATABASE_NAME = "cti_mongo_db"
APPLICATIONS_COLLECTION = "applications"
ACCELERATE_FLEX_COLLECTION = "accelerate_flex"
PATHWAY_GOALS_COLLECTION = "pathway_goals"
COURSES_COLLECTION = "courses"
