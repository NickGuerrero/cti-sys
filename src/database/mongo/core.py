import json
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from bson import json_util

from src.config import settings, MONGO_DATABASE_NAME
from src.database.mongo.service import init_collections

if not settings.cti_mongo_url:
    raise ValueError("MongoDB URL environment variable not found")

# Create a new client and connect to the server
client = MongoClient(settings.cti_mongo_url, server_api=ServerApi('1'))

# Send a ping to confirm a successful connection
def ping_mongo(client: MongoClient):
	client.admin.command('ping')

def get_mongo():
    "**Deprecated** for direct operations to DB collections, use `make_mongo_session` instead."
    return client[MONGO_DATABASE_NAME]

def make_mongo_session():
    """
    Dependency starts and yields a MongoDB ClientSession.

    After closure of utilizing scope, session will finish and abort started transaction.
    """
    client_session = client.start_session()
    try:
        yield client_session
    finally:
        client_session.end_session()

def init_mongo():
    init_collections(get_mongo())

async def close_mongo():
    return client.close()

def parse_bson(data):
    return json.loads(json_util.dumps(data))
