from typing import Any, Dict, Sequence
from pymongo import IndexModel
from pymongo.database import Database

from src.config import ACCELERATE_FLEX_COLLECTION, APPLICATIONS_COLLECTION, PATHWAY_GOALS_COLLECTION

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
    ),
    ACCELERATE_FLEX_COLLECTION: CollectionProps(
        schema={
            "bsonType": "object",
            "title": "Accelerate Flex Object Validation",
            "required": ["cti_id", "selected_deep_work", "academic_goals", "phone", "academic_year", "grad_year", "summers_left", "cs_exp", "cs_courses", "math_courses", "program_expectations", "career_outlook", "heard_about"],
            "properties": {
                "cti_id": {},
                "selected_deep_work": {},
                "academic_goals": {},
                "phone": {},
                "academic_year": {},
                "grad_year": {},
                "summers_left": {},
                "cs_exp": {},
                "cs_courses": {},
                "math_courses": {},
                "program_expectations": {},
                "career_outlook": {},
                "heard_about": {},
            },
            "additionalProperties": True
        },
        indexes=[

        ]
    ),
    PATHWAY_GOALS_COLLECTION: CollectionProps(
        schema={
            "bsonType": "object",
            "title": "Pathway Goals Object Validation",
            "required": ["pathway_desc", "course_req"],
            "properties": {
                "pathway_desc": {},
                "course_req": {},
            }
        },
        indexes=[

        ]
    )
}

def init_collections(mongo: Database, with_validators=True):
    """Initializes collections and their indexes"""
    existing_collections = set(mongo.list_collection_names())

    # if the collection exists, update with db.command; else create the collection
    for collection_name, collection_props in collections.items():
        if collection_name not in existing_collections:
            # create the schema with the above defined JSON schema given with_validators option
            if with_validators:
                mongo.create_collection(
                    collection_name,
                    validator={"$jsonSchema": collection_props.schema},
                    validationLevel="moderate" # validates on writes
                )
            else:
                mongo.create_collection(collection_name)

            # if the collection requires indexes, include them upon creation
            if len(collection_props.indexes) > 0:
                mongo.get_collection(collection_name).create_indexes(collection_props.indexes)
        else:
            mongo.command({
                "collMod": collection_name,
                "validator": {"$jsonSchema": collection_props.schema},
                "validationLevel": "moderate"
            })
