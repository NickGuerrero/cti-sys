from os import environ
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

from src.app.models.mongo.schemas import init_schemas
from src.config import MONGO_DATABASE_NAME

mongo_url = environ.get("CTI_MONGO_URL")
# Create a new client and connect to the server
client = MongoClient(mongo_url, server_api=ServerApi('1'))
# Send a ping to confirm a successful connection
def ping_mongo(client: MongoClient):
    try:
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        print(e)

def get_mongo():
    return client[MONGO_DATABASE_NAME]

def init_mongo():
    init_schemas(get_mongo())

async def close_mongo():
    return client.close()
