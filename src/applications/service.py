from datetime import datetime, timezone
from pymongo.database import Database

from src.applications.models import ApplicationModel
from src.applications.schemas import ApplicationCreateRequest
from src.config import APPLICATIONS_COLLECTION

def create(*, application_create: ApplicationCreateRequest, db: Database) -> ApplicationModel:
    application_collection = db.get_collection(APPLICATIONS_COLLECTION)

    # validate that required model params are present
    # Pydantic catches and raises its own code 422 on a failed Model.model_validate() call
    validated_app = ApplicationCreateRequest.model_validate(application_create)

    # add extra form attributes from application body data
    validated_with_extras = validated_app.model_dump()
    extras = application_create.model_extra or {}
    for prop, value in extras.items():
        validated_with_extras[prop] = value

    # set time of application submission
    validated_with_extras["app_submitted"] = datetime.now(timezone.utc)

    # set default tracking attributes of application submission
    application_with_defaults = ApplicationModel.model_validate(validated_with_extras)

    # insert the document with required and flexible form responses
    app_result = application_collection.insert_one(application_with_defaults.model_dump())

    created_app: ApplicationModel = application_collection.find_one({
        "_id": app_result.inserted_id
    })

    return created_app
