from enum import Enum

class EnrollmentRole(Enum):
    """
    Enum values for Canvas SIS Import of Enrollments.csv `role` column.
    """
    STUDENT = "student"
    TEACHER = "teacher"
    TA = "ta"
    OBSERVER = "observer"
    DESIGNER = "designer"

class EnrollmentStatus(Enum):
    """
    Enum values for Canvas SIS Import of Enrollments.csv `status` column.
    """
    ACTIVE = "active"
    DELETED = "deleted"
    COMPLETED = "completed"
    INACTIVE = "inactive"
    DELETED_LAST_COMPLETED = "deleted_last_completed"

class UserStatus(Enum):
    """
    Enum values for Canvas SIS Import of Users.csv `status` column.
    """
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"
