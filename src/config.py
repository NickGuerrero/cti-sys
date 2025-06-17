from pydantic_settings import BaseSettings

# Consider moving into a pydantic-settings package's `class Settings(BaseSettings)` for environment-specific overrides

class Settings(BaseSettings):
    app_env: str = "development"
    unterview_course_id: int = 161
    unterview_sis_course_id: str = "S161"
    current_unterview_sis_section_id: str = "S194" # NOTE had to manually define this in Canvas
    current_unterview_section_id: int = 194
    canvas_api_url: str = "https://cti-courses.instructure.com"
    canvas_api_test_url: str = "https://cti-courses.test.instructure.com"

    model_config = {
        "case_sensitive": False,
    }

settings = Settings()

# MongoDB
MONGO_DATABASE_NAME = "cti_mongo_db"

APPLICATIONS_COLLECTION = "applications"
ACCELERATE_FLEX_COLLECTION = "accelerate_flex"
PATHWAY_GOALS_COLLECTION = "pathway_goals"
COURSES_COLLECTION = "courses"
