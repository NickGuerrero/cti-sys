from typing import Annotated
from pydantic import BeforeValidator

# https://www.mongodb.com/developer/languages/python/python-quickstart-fastapi/#database-models
# required to properly encode bson ObjectId to str on Mongo documents
PyObjectId = Annotated[str, BeforeValidator(str)]
