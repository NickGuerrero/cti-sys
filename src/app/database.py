from os import environ
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Note: We instantiate Base here because a single Base object will hold the Metadata
# Calling it in either models or main would desynchronize the ORM, as far as I'm concerned
class Base(DeclarativeBase):
    pass

url = URL.create(
    drivername="postgresql+psycopg",
    username=environ.get("USERNAME"),
    password=environ.get("PASSWORD"),
    host=environ.get("HOST"),
    database=environ.get("DATABASE"),
    port=environ.get("PORT")
)
engine = create_engine(url,
    connect_args={"sslmode": environ.get("SSLMODE")})

# Session Management
SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
def make_session():
    new_session = SessionFactory()
    try:
        yield new_session
    finally:
        new_session.close()