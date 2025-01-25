from pymongo.database import Database

from src.config import APPLICATIONS_COLLECTION

collections = {
    APPLICATIONS_COLLECTION: {
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
    }
}

def init_schemas(mongo: Database):
    exitingCollections = set(mongo.list_collection_names())

    # if the collection exists, update with db.command; else create the collection
    for collection in collections:
        if collection not in exitingCollections:
            mongo.create_collection(
            collection,
            validator={"$jsonSchema": collections[collection]},
            validationLevel="moderate" # validates on write
            )
        else:
            mongo.command({
            "collMod": collection,
            "validator": {"$jsonSchema": collections[collection]},
            "validationLevel": "moderate"
})