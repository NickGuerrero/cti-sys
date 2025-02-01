from typing import Any, Dict, Sequence
from pymongo import IndexModel
from pymongo.database import Database

from src.config import APPLICATIONS_COLLECTION

class CollectionProps:
    def __init__(self, schema: Dict[str, Any], indexes: Sequence[IndexModel]):
        # schema as it will be stored and validated internally on MongoDB
        self.schema = schema
        # indexes for the collection
        self.indexes = indexes

collections: dict[str, CollectionProps] = {
    APPLICATIONS_COLLECTION: CollectionProps(
        schema={
            "bsonType": "object",
            "title": "Application Object Validation",
            "required": ["email", "fname", "lname", "app_submitted"],
            "properties": {
                "email": {
                    "bsonType": "string",
                    "pattern": "^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$",
                    "description": "Must provide a valid email address"
                },
                "fname": {
                    "bsonType": "string",
                    "description": "Must provide a first name of minimum length 1",
                    "minLength": 1
                },
                "lname": {
                    "bsonType": "string",
                    "description": "Must provide a last name of minimum length 1",
                    "minLength": 1
                },
                "app_submitted": {
                    "bsonType": "date",
                    "description": "Must provide the date at which the application was submitted as UTC datetime"
                },
            },
            "additionalProperties": True
        },
        indexes=[
            IndexModel("email", unique=True)
        ]
    )
}

def init_schemas(mongo: Database):
    existing_collections = set(mongo.list_collection_names())

    # if the collection exists, update with db.command; else create the collection
    for collection_name, collection_props in collections.items():
        if collection_name not in existing_collections:
            # create the schema with the above defined JSON schema
            mongo.create_collection(
                collection_name,
                validator={"$jsonSchema": collection_props.schema},
                validationLevel="moderate" # validates on writes
            )
            # if the collection requires indexes, include them upon creation
            if len(collection_props.indexes) > 0:
                mongo.get_collection(collection_name).create_indexes(collection_props.indexes)
        else:
            mongo.command({
                "collMod": collection_name,
                "validator": {"$jsonSchema": collection_props.schema},
                "validationLevel": "moderate"
            })
