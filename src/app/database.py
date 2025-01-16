from os import environ
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Note: We instantiate Base here because a single Base object will hold the Metadata
# Calling it in either models or main would desynchronize the ORM, as far as I'm concerned
class Base(DeclarativeBase):
    pass

# Toggle determines whether to load an env file, or if env variables are already loaded
# Gunicorn will not run on Windows, so the path does not need to be system agnostic
# Default False (cloud environment) TODO: Move this elsewhere that's more universal
env_required = False
if env_required:
    load_dotenv(dotenv_path="./../../.env")

# Engine & Session Configuration
# Note that currently, sessions are the only way to interface with the database
engine = create_engine(environ.get("CTI_POSTGRES_URL"))
SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def make_session(SessionFactory):
    new_session = SessionFactory()
    try:
        yield new_session
    finally:
        new_session.close()