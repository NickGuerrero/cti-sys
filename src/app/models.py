from sqlalchemy import Column, Integer, String, Date, Boolean
from .database import Base

class Student(Base):
    __tablename__ = "students"
    cti_id = Column(Integer, primary_key=True)
    fname = Column(String(100))
    pname = Column(String(100))
    lname = Column(String(100))
    join_date = Column(Date)
    target_year = Column(Integer)
    gender = Column(String(50))
    first_gen = Column(Boolean)
    institution = Column(String(255))
    is_graduate = Column(Boolean)
    birthday = Column(Date)
    active = Column(Boolean)
    cohort_lc = Column(Boolean)