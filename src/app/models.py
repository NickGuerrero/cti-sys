from sqlalchemy import (
    Integer, String, Date, Boolean, DateTime, Float, TimeStamp,
    ForeignKey
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from .database import Base

# TODO: FKs, Composite keys, and proper table definitions
# For PG, consider removing length limit (https://wiki.postgresql.org/wiki/Don%27t_Do_This#Don.27t_use_varchar.28n.29_by_default)
class Student(Base):
    __tablename__ = "students"
    cti_id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    fname: Mapped[str] = mapped_column(String, nullable=False)
    pname: Mapped[str] = mapped_column(String)
    lname: Mapped[str] = mapped_column(String, nullable=False)
    join_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    target_year: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[str] = mapped_column(String)
    first_gen: Mapped[bool] = mapped_column(Boolean)
    institution: Mapped[str] = mapped_column(String)
    is_graduate: Mapped[bool] = mapped_column(Boolean)
    birthday: Mapped[date] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean)
    cohort_lc: Mapped[bool] = mapped_column(Boolean)

class StudentEmail(Base):
    __tablename__ = "student_emails"
    email: Mapped[str] = mapped_column(String, primary_key=True)
    cti_id: Mapped[int] = mapped_column(Integer) # Index here
    is_primary: Mapped[bool] = mapped_column(Boolean)

class CanvasID(Base):
    __tablename__ = "canvas_ids"
    cti_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    canvas_id: Mapped[int] = mapped_column(Integer) # Index here

class Ethnicity(Base):
    __tablename__ = "ethnicities"
    cti_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ethnicity: Mapped[str] = mapped_column(String)
    details: Mapped[str] = mapped_column(String) # We may need this to be Text

class StudentAttendance(Base):
    __tablename__ = "student_attendance"
    cti_id: Mapped[int] = mapped_column(Integer) # PK
    session_id: Mapped[int] = mapped_column(Integer) # PK
    peardeck_score: Mapped[float] = mapped_column(Float(3))
    attended_minutes: Mapped[int] = mapped_column(Integer)
    session_score: Mapped[float] = mapped_column(Float(3))

class Attendance(Base):
    __tablename__ = "attendance"
    session_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_start: Mapped[datetime] = mapped_column(DateTime)
    session_end: Mapped[datetime] = mapped_column(DateTime)
    program: Mapped[str] = mapped_column(String)
    session_type: Mapped[str] = mapped_column(String)
    link_type: Mapped[str] = mapped_column(String)
    link: Mapped[str] = mapped_column(String)
    owner: Mapped[str] = mapped_column(String)
    last_processed_date: Mapped[datetime] = mapped_column(DateTime)

class MissingAttendance(Base):
    __tablename__ = "missing_attendance"
    email: Mapped[str] = mapped_column(String)
    session_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String)
    peardeck_score: Mapped[int] = mapped_column(Float(3))
    attended_minutes: Mapped[int] = mapped_column(Integer)