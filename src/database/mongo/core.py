import json
from os import environ
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from bson import json_util

from dotenv import load_dotenv  # added

from src.config import MONGO_DATABASE_NAME
from src.database.mongo.service import init_collections

load_dotenv() # added
MONGO_URL = environ.get("CTI_MONGO_URL")
if not MONGO_URL:
    raise ValueError("MongoDB URL environment variable not found")

# Create a new client and connect to the server
client = MongoClient(MONGO_URL, server_api=ServerApi('1'))

# Send a ping to confirm a successful connection
def ping_mongo(client: MongoClient):
	client.admin.command('ping')

def get_mongo():
    return client[MONGO_DATABASE_NAME]

def init_mongo():
    init_collections(get_mongo())

async def close_mongo():
    return client.close()

def parse_bson(data):
    return json.loads(json_util.dumps(data))
