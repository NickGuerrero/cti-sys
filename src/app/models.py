from sqlalchemy import Column, Integer, String, Boolean
from .database import Base

class Student(Base):
    __tablename__ = "users"
    cti_id = Column(Integer, primary_key=True)
    fname = Column(String)