from typing import Annotated
from pydantic import BaseModel, BeforeValidator, ConfigDict

# Mongo Schemas...
# https://www.mongodb.com/developer/languages/python/python-quickstart-fastapi/#database-models
# required to properly encode bson ObjectId to str on Mongo documents
PyObjectId = Annotated[str, BeforeValidator(str)]

# Postgres Schemas...
class ORMSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
