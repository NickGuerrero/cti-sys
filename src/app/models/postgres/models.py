from sqlalchemy import (
    Integer, String, Date, Boolean, DateTime, Float,
    ForeignKey, ForeignKeyConstraint, func, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from typing import List, Optional
from ...database import Base

# TODO: Determine which back_populates are needed WIP
# TODO: Get test data set-up, maybe a larger set WIP
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
    pname: Mapped[Optional[str]] = mapped_column(String)
    lname: Mapped[str] = mapped_column(String, nullable=False)
    join_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.CURRENT_TIMESTAMP(), nullable=False)
    target_year: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[Optional[str]] = mapped_column(String)
    first_gen: Mapped[Optional[bool]] = mapped_column(Boolean)
    institution: Mapped[Optional[str]] = mapped_column(String)
    is_graduate: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)
    birthday: Mapped[Optional[date]] = mapped_column(Date) # If null, assume student is at least 18
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    cohort_lc: Mapped[bool] = mapped_column(Boolean, default=False)
    # Relationships
    email_addresses: Mapped[List["StudentEmail"]] = relationship(back_populates="email_owner")
    canvas_id: Mapped["CanvasID"] = relationship(back_populates="id_owner")
    ethnicities: Mapped[List["Ethnicity"]] = relationship(back_populates="eth_owner")
    # Note: Attendance relationship removed, use joins for explicit attendance processes

class StudentEmail(Base):
    __tablename__ = "student_emails"
    email: Mapped[str] = mapped_column(String, primary_key=True)
    cti_id: Mapped[int] = mapped_column(ForeignKey("students.cti_id"))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_owner: Mapped["Student"] = relationship(back_populates="email_addresses")

    __table_args__ = (
        # Unique index: Make sure each individual cti_id has only 1 primary email
        Index("single_primary_email", "cti_id", postgresql_where=(is_primary.is_(True)), unique=True)
    )

class CanvasID(Base):
    __tablename__ = "canvas_ids"
    cti_id: Mapped[int] = mapped_column(ForeignKey("students.cti_id"), primary_key=True)
    canvas_id: Mapped[int] = mapped_column(Integer, nullable=False)
    id_owner: Mapped["Student"] = relationship(back_populates="canvas_id")

    __table_args__ = (
        # Index on Canvas ID
        Index("unique_canvas_id", "canvas_id", unique=True)
    )

class Ethnicity(Base):
    __tablename__ = "ethnicities"
    cti_id: Mapped[int] = mapped_column(ForeignKey("students.cti_id"), primary_key=True)
    ethnicity: Mapped[str] = mapped_column(String, default="DNE", primary_key=True)
    details: Mapped[Optional[str]] = mapped_column(String)
    eth_owner: Mapped["Student"] = relationship(back_populates="canvas_id")

##################################
# Attendance Data
##################################
class Attendance(Base):
    __tablename__ = "attendance"
    session_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    session_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    program: Mapped[str] = mapped_column(String) # Accelerate, ISS, SOSE, Launch, etc.
    session_type: Mapped[str] = mapped_column(String) # Deep Work, Guided, Hack Session
    link_type: Mapped[str] = mapped_column(String, default="peardeck") # PearDeck
    link: Mapped[str] = mapped_column(String) # URL
    owner: Mapped[str] = mapped_column(String) # Who owns the file
    last_processed_date: Mapped[Optional[datetime]] = mapped_column(DateTime) # null means not processed
    # Relationships
    attendances: Mapped[List["StudentAttendance"]] = relationship(back_populates="session")
    missing_records: Mapped[List["MissingAttendance"]] = relationship(back_populates="session")

class StudentAttendance(Base):
    __tablename__ = "student_attendance"
    cti_id: Mapped[int] = mapped_column(ForeignKey("students.cti_id"), primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("attendance.session_id"), primary_key=True)
    peardeck_score: Mapped[float] = mapped_column(Float(3), default=0)
    attended_minutes: Mapped[int] = mapped_column(Integer, default=0)
    session_score: Mapped[float] = mapped_column(Float(3), default=0)
    # Relationships
    session: Mapped["Attendance"] = relationship(back_populates="attendances")

class MissingAttendance(Base):
    __tablename__ = "missing_attendance"
    email: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("attendance.session_id"), primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String)
    peardeck_score: Mapped[Optional[int]] = mapped_column(Float(3))
    attended_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    # Relationships
    session: Mapped["Attendance"] = relationship(back_populates="missing_records")

##################################
# Accelerate Records
##################################

class Accelerate(Base):
    __tablename__ = "accelerate"
    cti_id: Mapped[int] = mapped_column(ForeignKey("students.cti_id"), primary_key=True)
    student_type: Mapped[str] = mapped_column(String, default="regular") # Regular, Wave 2, other classifications
    target_year: Mapped[int] = mapped_column(Integer) # 2024 - 2025 => 2025
    accountability_group: Mapped[Optional[str]] = mapped_column(String)
    accountability_team: Mapped[Optional[int]] = mapped_column(Integer)
    pathway_goal: Mapped[str] = mapped_column(String) # Summer Tech Internship, REU, etc.
    participation_score: Mapped[Optional[float]] = mapped_column(Float(3))
    sessions_attended: Mapped[int] = mapped_column(Integer, default=0)
    participation_streak: Mapped[int] = mapped_column(Integer, default=0)
    returning_student: Mapped[bool] = mapped_column(Boolean, default=False)
    inactive_weeks: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Relationships
    progress_record: Mapped["AccelerateCourseProgress"] = relationship(back_populates="owner")
    ag_record: Mapped["AccountabilityGroup"] = relationship(back_populates="owner")

# Note: Columns seperated from above table since progress may be handled differently
class AccelerateCourseProgress(Base):
    __tablename__ = "accelerate_course_progress"
    cti_id: Mapped[int] = mapped_column(ForeignKey("students.cti_id"), primary_key=True)
    latest_course: Mapped[Optional[str]] = mapped_column(String)
    latest_milestone: Mapped[Optional[str]] = mapped_column(String)
    pathway_score: Mapped[Optional[float]] = mapped_column(Float(3))
    pathway_difference: Mapped[Optional[int]] = mapped_column(Integer)
    owner: Mapped["Accelerate"] = relationship(back_populates="progress_record")

class AccountabilityGroup(Base):
    __tablename__ = "accountability_group"
    accountability_group: Mapped[str] = mapped_column(ForeignKey("accelerate.accountability_group"), primary_key=True)
    student_accelerator: Mapped[str] = mapped_column(String)
    owner: Mapped["Accelerate"] = relationship(back_populates="ag_record")