from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

def handle_db_exceptions(db: Session, exc: Exception) -> None:
    """
    Roll back the transaction and raise a consistent HTTPException based on the error type.
    """
    db.rollback()

    if isinstance(exc, SQLAlchemyError):
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")
    elif isinstance(exc, HTTPException):
        raise exc
    else:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}")
