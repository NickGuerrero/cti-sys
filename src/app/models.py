from sqlalchemy import (
    Integer, String, Date, Boolean, DateTime, Float,
    ForeignKey, ForeignKeyConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from typing import List
from .database import Base

# TODO: FKs, Composite keys, and proper table definitions
# For PG, consider removing length limit (https://wiki.postgresql.org/wiki/Don%27t_Do_This#Don.27t_use_varchar.28n.29_by_default)
# Composite foriegn keys: https://stackoverflow.com/questions/75747252/using-sqlalchemy-orm-with-composite-primary-keys

###
# Core Student Data: Shared across all programs
###
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
    # Relationships
    email_addresses: Mapped[List["StudentEmail"]] = relationship(back_populates="email_owner")
    canvas_id: Mapped["CanvasID"] = relationship(back_populates="id_owner")
    ethnicities: Mapped["Ethnicity"] = relationship(back_populates="eth_owner")
    attendances: Mapped[List["StudentAttendance"]] = relationship(back_populates="student")

class StudentEmail(Base):
    __tablename__ = "student_emails"
    email: Mapped[str] = mapped_column(String, primary_key=True)
    cti_id: Mapped[int] = mapped_column(ForeignKey("students.cti_id")) # TODO: Index here
    is_primary: Mapped[bool] = mapped_column(Boolean)
    email_owner: Mapped["Student"] = relationship(back_populates="email_addresses")

class CanvasID(Base):
    __tablename__ = "canvas_ids"
    cti_id: Mapped[int] = mapped_column(ForeignKey("students.cti_id"), primary_key=True)
    canvas_id: Mapped[int] = mapped_column(Integer) # Index here
    id_owner: Mapped["Student"] = relationship(back_populates="canvas_id")

class Ethnicity(Base):
    __tablename__ = "ethnicities"
    cti_id: Mapped[int] = mapped_column(ForeignKey("students.cti_id"), primary_key=True)
    ethnicity: Mapped[str] = mapped_column(String)
    details: Mapped[str] = mapped_column(String)
    eth_owner: Mapped["Student"] = relationship(back_populates="canvas_id")

##################################
# Attendance Data
##################################
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
    # Relationships
    attendances: Mapped[List["StudentAttendance"]] = relationship(back_populates="session")
    missing_records: Mapped[List["MissingAttendance"]] = relationship(back_populates="session")

class StudentAttendance(Base):
    __tablename__ = "student_attendance"
    cti_id: Mapped[int] = mapped_column(ForeignKey("students.cti_id"), primary_key=True) # PK
    session_id: Mapped[int] = mapped_column(ForeignKey("attendance.session_id"), primary_key=True) # PK
    peardeck_score: Mapped[float] = mapped_column(Float(3))
    attended_minutes: Mapped[int] = mapped_column(Integer)
    session_score: Mapped[float] = mapped_column(Float(3))
    # Relationships
    student: Mapped["Student"] = relationship(back_populates="attendances")
    session: Mapped["Attendance"] = relationship(back_populates="attendances")
    __table_args__ = (
        ForeignKeyConstraint(
            [cti_id, session_id], [Student.cti_id, Attendance.session_id]
        ),
    )

class MissingAttendance(Base):
    __tablename__ = "missing_attendance"
    email: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String)
    peardeck_score: Mapped[int] = mapped_column(Float(3))
    attended_minutes: Mapped[int] = mapped_column(Integer)
    # Relationships
    session: Mapped["Attendance"] = relationship(back_populates="missing_records")