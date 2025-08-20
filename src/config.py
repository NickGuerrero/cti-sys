import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    # NOTE SIS section ids need to be manually defined in Canvas
    # Go to Settings -> Sections -> Your Section -> Set SIS ID
    app_env: str = os.getenv("APP_ENV")
    unterview_course_id: int = os.getenv("COURSE_ID_UNTERVIEW")
    unterview_sis_course_id: str = os.getenv("UNTERVIEW_SIS_COURSE_ID")
    current_unterview_sis_section_id: str = os.getenv("CUR_UNTERVIEW_SIS_SECTION_ID")
    current_unterview_section_id: int = os.getenv("CUR_UNTERVIEW_SECTION_ID")
    course_id_101: int = os.getenv("COURSE_ID_101")
    commitment_quiz_id: int = os.getenv("COMMITMENT_QUIZ_ID")
    canvas_api_url: str = "https://cti-courses.test.instructure.com"
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
