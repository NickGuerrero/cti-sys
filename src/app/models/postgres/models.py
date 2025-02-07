from sqlalchemy import (
    Integer, String, Date, Boolean, DateTime, Float,
    ForeignKey, ForeignKeyConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from typing import List
from ...database import Base

# TODO: Add nullable columns
# TODO: Determine which back_populates are needed
# TODO: Get test data set-up, maybe a larger set
# TODO: Also, Alembic's not working. It's probably a file path issue
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
    is_primary: Mapped[bool] = mapped_column(Boolean) # TODO: Make sure each individual cti_id has only 1 primary email
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

class MissingAttendance(Base):
    __tablename__ = "missing_attendance"
    email: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String)
    peardeck_score: Mapped[int] = mapped_column(Float(3))
    attended_minutes: Mapped[int] = mapped_column(Integer)
    # Relationships
    session: Mapped["Attendance"] = relationship(back_populates="missing_records")

class Accelerate(Base):
    __tablename__ = "accelerate"
    cti_id: Mapped[int] = mapped_column(ForeignKey("students.cti_id"), primary_key=True)
    student_type: Mapped[str] = mapped_column(String)
    accelerate_year: Mapped[int] = mapped_column(Integer)
    accountability_group: Mapped[str] = mapped_column(String)
    accountability_team: Mapped[int] = mapped_column(Integer)
    pathway_goal: Mapped[str] = mapped_column(String)
    participation_score: Mapped[float] = mapped_column(Float(3))
    sessions_attended: Mapped[int] = mapped_column(Integer)
    participation_streak: Mapped[int] = mapped_column(Integer)
    returning_student: Mapped[bool] = mapped_column(Boolean)
    inactive_weeks: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean)

class AccelerateCourseProgress(Base):
    __tablename__ = "accelerate_course_progress"
    cti_id: Mapped[int] = mapped_column(ForeignKey("students.cti_id"), primary_key=True)
    latest_course: Mapped[str] = mapped_column(String)
    latest_milestone: Mapped[str] = mapped_column(String)
    pathway_score: Mapped[float] = mapped_column(Float(3))
    pathway_difference: Mapped[int] = mapped_column(Integer)

class AccountabilityGroup(Base):
    __tablename__ = "accountability_group"
    accountability_group: Mapped[str] = mapped_column(ForeignKey("accelerate.accountability_group"), primary_key=True)
    student_accelerator: Mapped[str] = mapped_column(String)