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
# Default False (cloud environment) TODO: Move this elsewhere that's more universal
env_required = False

if env_required:
    load_dotenv(dotenv_path=".\..\..\.env")

engine = create_engine(environ.get("CTI_POSTGRES_URL"))

# Session Management
SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
def make_session():
    new_session = SessionFactory()
    try:
        yield new_session
    finally:
        new_session.close()