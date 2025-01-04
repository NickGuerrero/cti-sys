from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .database import make_session
from .models import Student
from .schemas import StudentSchema

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "cti-sys v1.0.0"}

@app.get("/test-db")
def database_test(db: Session = Depends(make_session)):
    try:
        exists = db.query(Student).first()
        if exists:
            return StudentSchema.model_validate(Student)
        else:
            return {"message": "Database Accessible, but contains no data"}
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database Inaccessible")