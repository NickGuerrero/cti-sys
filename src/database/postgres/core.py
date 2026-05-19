from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.config import settings

# Note: We instantiate Base here because a single Base object will hold the Metadata
# Calling it in either models or main would desynchronize the ORM, as far as I'm concerned
class Base(DeclarativeBase):
    pass

# Engine & Session Configuration
# Note that currently, sessions are the only way to interface with the database
engine = create_engine(settings.cti_postgres_url)
SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def make_session():
    new_session = SessionFactory()
    try:
        yield new_session
    finally:
        new_session.close()