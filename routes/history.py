from fastapi import APIRouter, Depends, HTTPException

from models import UserProfile
from routes.auth import get_current_user, get_store


router = APIRouter(prefix="/history")


@router.get("/")
async def list_history(current_user: UserProfile = Depends(get_current_user)):
    entries = get_store().list_history(current_user.email)
    return [
        {
            "id": entry.id,
            "language": entry.language,
            "risk_level": entry.risk_level,
            "vulnerability_count": entry.vulnerability_count,
            "analysis_date": entry.analysis_date,
            "findings": entry.findings,
        }
        for entry in entries
    ]


@router.delete("/{entry_id}")
async def delete_history(entry_id: str, current_user: UserProfile = Depends(get_current_user)):
    deleted = get_store().delete_history(current_user.email, entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="History entry not found")
    return {"message": "History entry deleted successfully"}