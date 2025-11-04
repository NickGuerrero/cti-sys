from typing import Any, Dict, Sequence
from pymongo import IndexModel
from pymongo.database import Database

from src.config import ACCELERATE_FLEX_COLLECTION, APPLICATIONS_COLLECTION, COURSES_COLLECTION, PATHWAY_GOALS_COLLECTION

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
            "required": ["email", "fname", "lname", "app_submitted", "canvas_id", "added_unterview_course", "next_steps_sent", "accessed_unterview", "commitment_quiz_completed", "master_added"],
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
                "canvas_id": {
                    "bsonType": ["int", "null"],
                    "description": "Must provide integer Canvas ID of applicant or set to null"
                },
                "added_unterview_course": {
                    "bsonType": "bool",
                    "description": "Must provide whether the applicant has been added as a CTI Canvas user as a boolean value"
                },
                "next_steps_sent": {
                    "bsonType": "bool",
                    "description": "Must provide whether the applicant has been sent their 'Next Steps' email as a boolean value"
                },
                "accessed_unterview": {
                    "bsonType": "bool",
                    "description": "Must provide whether the applicant has accessed unterview as a boolean value"
                },
                "commitment_quiz_completed": {
                    "bsonType": "bool",
                    "description": "Must provide whether the applicant has completed the commitment quiz as a boolean value"
                },
                "master_added": {
                    "bsonType": "bool",
                    "description": "Must provide whether the applicant has been added to the Master Roster as a boolean value"
                }
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
            "required": ["cti_id"],
            "properties": {
                "cti_id": {
                    "bsonType": "int",
                    "description": "Must include the ID derived from Postgres database's Student table PK as an integer value"
                },
                "selected_deep_work": {
                    "bsonType": ["object", "null"],
                    "required": ["day", "time", "sprint"],
                    "properties": {
                        "day": {
                            "bsonType": "string",
                            "description": "Must include the weekday of the deepwork session as a string value"
                        },
                        "time": {
                            "bsonType": "string",
                            "description": "Must include the start and end time of the deepwork session as a string value (ex: '2pm - 4pm')"
                        },
                        "sprint": {
                            "bsonType": "string",
                            "description": "Must include the sprint this deepwork session is associated with"
                        }
                    }
                },
                "academic_goals": {
                    "bsonType": ["array", "null"],
                    "description": "Must include academic goals as an array of string values"
                },
                "phone": {
                    "bsonType": ["string", "null"],
                    "description": "Must include phone number of student as a string value"
                },
                "academic_year": {
                    "bsonType": ["int", "null"],
                    "description": "Must include number of years student has done in college (e.g. 0 for first-year, 1 second-year)"
                },
                "grad_year": {
                    "bsonType": ["string", "null"],
                    "description": "Must include expected graduation year as string (e.g. Spring 2026, Fall 2027)"
                },
                "summers_left": {
                    "bsonType": ["int", "null"],
                    "description": "Must include number of summers remaining before graduation as an integer value"
                },
                "cs_exp": {
                    "bsonType": ["bool", "null"],
                    "description": "Must include whether a CS course has been taken before as a boolean value"
                },
                "cs_courses": {
                    "bsonType": ["array", "null"],
                    "description": "Must include CS courses taken as a array using a string value for each course"
                },
                "math_courses": {
                    "bsonType": ["array", "null"],
                    "description": "Must include math courses taken as a array using a string value for each course"
                },
                "program_expectation": {
                    "bsonType": ["string", "null"],
                    "description": "Must include what student hopes to get out of the program as a string value"
                },
                "career_outlook": {
                    "bsonType": ["string", "null"],
                    "description": "Must include where student sees themselves in 2-4 years as a string value"
                },
                "heard_about": {
                    "bsonType": ["string", "null"],
                    "description": "Must include how student heard about Accelerate as a string value"
                },
            },
            "additionalProperties": True
        },
        indexes=[
            IndexModel("cti_id", unique=True)
        ]
    ),
    PATHWAY_GOALS_COLLECTION: CollectionProps(
        schema={
            "bsonType": "object",
            "title": "Pathway Goals Object Validation",
            "required": ["pathway_goal"],
            "properties": {
                "pathway_goal": {
                    "bsonType": "string",
                    "description": "Must include the pathway goal as a string value (ex: 'Summer Tech Internship 2025')"
                },
                "pathway_desc": {
                    "bsonType": ["string", "null"],
                    "description": "Must include the pathway goal description as a string value (ex: 'Obtain a summer tech internship for 2025')"
                },
                "course_req": {
                    "bsonType": ["array", "null"],
                    "description": "Must include the course requirements as 'courses' collection course_id values of the pathway goal as an array of string values"
                },
            }
        },
        indexes=[
            IndexModel("pathway_goal", unique=True)
        ]
    ),
    COURSES_COLLECTION: CollectionProps(
        schema={
            "bsonType": "object",
            "title": "Courses Object Validation",
            "required": ["course_id"],
            "properties": {
                "course_id": {
                    "bsonType": "string",
                    "description": "Must include the name/codeword of the course as a string value"
                },
                "canvas_id": {
                    "bsonType": ["int", "null"],
                    "description": "Must include the course's id on canvas as an integer value"
                },
                "title": {
                    "bsonType": ["string", "null"],
                    "description": "Must include the course title as a string value"
                },
                "milestones": {
                    "bsonType": ["array", "null"],
                    "description": "Must include the number of assignments to complete each milestone ([1 - n]) as an integer array value"
                },
                "version": {
                    "bsonType": ["string", "null"],
                    "description": "Must include the version number for this course as a string value"
                },
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
