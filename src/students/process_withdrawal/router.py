from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.database.postgres.core import make_session
from src.students.process_withdrawal.schemas import ProcessWithdrawalRequest 
from src.students.process_withdrawal.service import process, fetch_inactive_record
from src.config import settings

router = APIRouter()

@router.post("", status_code=status.HTTP_200_OK)
def process_withdrawal(
    request: ProcessWithdrawalRequest, 
    db: Session = Depends(make_session),
):
    """
    Endpoint to process responses form the withdrawal form.
    Create a one-time passcode link to mark themselves inactive.
    Store this record in the inactive_requests with a timestamp.
    """
    try: 
        # Execute the email modification logic.
        email = process(request=request, db=db)

        # In production, return a basic status message.
        if settings.app_env == "production":
            return {"status": 200}
        else: 
            # In non production environments, return saved record from database
            record = fetch_inactive_record(request.auto_email.lower(), db=db)
            return {
                "status": 200,
                "id": record["id"],
                "passkey": record["passkey"],
                "timestamp": record["timestamp"],
            }
    
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except HTTPException as http_exc:
        db.rollback()
        raise http_exc
    except Exception as e:
        print("Error HERE: " + str(e))
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    
