from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Note: We instantiate Base here because a single Base object will hold the Metadata
# Calling it in either models or main would desynchronize the ORM, as far as I'm concerned
class Base(DeclarativeBase):
    pass

url = URL.create(
    drivername="postgresql",
    username="<your-username>",
    password="<your-pass>",
    host="localhost",
    database="mydb",
    port=5432
)
engine = create_engine(url)

# Session Management
SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
def make_session():
    new_session = SessionFactory()
    try:
        yield new_session
    finally:
        new_session.close()