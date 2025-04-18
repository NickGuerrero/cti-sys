from pydantic_settings import BaseSettings

# Consider moving into a pydantic-settings package's `class Settings(BaseSettings)` for environment-specific overrides

class Settings(BaseSettings):
    app_env: str = "development"
    unterview_id: int = 5
    current_section: str = "Target Summer 2025"
    canvas_api_url: str = "https://cti-courses.test.instructure.com" # NOTE test env not consistent

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
