from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

from .app.database import make_session
from .app.models import Student
from .app.schemas import StudentSchema

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "cti-sys v1.0.0"}

@app.get("/test-connection")
def confirm_conn(db: Session = Depends(make_session)):
    return db.get_bind()
    try:
        result = db.execute(text("SELECT 1"))
        if result.scalar() == 1:
            return {"message": "Database connection succeeded"}
    except SQLAlchemyError as e:
        return e
        #raise HTTPException(status_code=500, detail="Database Inaccessible")

@app.get("/test-db")
def database_test(db: Session = Depends(make_session)):
    return db.get_bind()
    try:
        exists = db.query(Student).first()
        if exists:
            return StudentSchema.model_validate(Student)
        else:
            return {"message": "Database Accessible, but contains no data"}
    except SQLAlchemyError as e:
        return e
        # raise HTTPException(status_code=500, detail="Database Inaccessible")