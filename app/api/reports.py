from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.db import schemas
from app.db.database import SessionLocal, get_db

router = APIRouter()

@router.get('/reports/{report_id}')
async def get_report(
    report_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific analysis report.
    
    ⚠️ PROTECTED ROUTE: Only verified and active users can access this endpoint.
    """
    # Verify user is in good standing
    user = schemas.get_user_by_id(db, current_user["user_id"])
    if not user or not user.verified or not user.active:
        raise HTTPException(
            status_code=403,
            detail="Your account is not verified or has been deactivated. Please contact admin."
        )
    
    report = schemas.get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail='Report not found')
    return report
