from os import environ
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

from src.config import MONGO_DATABASE_NAME

mongoURL = environ.get("CTI_MONGO_URL")
# Create a new client and connect to the server
client = MongoClient(mongoURL, server_api=ServerApi('1'))
# Send a ping to confirm a successful connection
def ping_mongo():
    try:
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        print(e)

def get_mongo():
    return client[MONGO_DATABASE_NAME]

async def close_mongo():
    return client.close()