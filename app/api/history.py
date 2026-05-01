"""
Analysis History API endpoints
Handles storing, retrieving, and managing user's code analysis history
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db import schemas
from app.core.security import get_current_user
import uuid
import logging

# Setup logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("/")
async def get_analysis_history(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's analysis history.
    
    Returns most recent analyses first (paginated).
    """
    try:
        logger.info(f"Fetching analysis history for user {current_user['user_id']}")
        
        # Verify user exists
        user = schemas.get_user_by_id(db, current_user["user_id"])
        if not user:
            logger.warning(f"User {current_user['user_id']} not found in database")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get analysis history
        histories = schemas.get_analysis_history(
            db,
            user_id=current_user["user_id"],
            limit=limit,
            offset=offset
        )
        
        logger.info(f"Found {len(histories)} analyses for user {user.email}")
        
        # Convert to dict format to avoid ORM issues
        data = []
        for h in histories:
            try:
                data.append({
                    "id": h.id,
                    "user_id": h.user_id,
                    "code_snippet": h.code_snippet,
                    "language": h.language,
                    "findings": h.findings,
                    "risk_level": h.risk_level,
                    "vulnerability_count": h.vulnerability_count,
                    "analysis_date": h.analysis_date.isoformat() if h.analysis_date else None,
                    "created_at": h.created_at.isoformat() if h.created_at else None,
                })
            except Exception as e:
                logger.error(f"Error converting history record {h.id}: {str(e)}")
                continue
        
        return {
            "total": len(data),
            "limit": limit,
            "offset": offset,
            "data": data
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error fetching analysis history: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching history: {str(e)}"
        )


@router.get("/{analysis_id}")
async def get_analysis_detail(
    analysis_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed view of a specific analysis.
    
    User can only access their own analyses.
    """
    try:
        # Get analysis and verify ownership
        analysis = schemas.get_analysis_by_id(
            db,
            user_id=current_user["user_id"],
            analysis_id=analysis_id
        )
        
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found or you don't have permission to access it"
            )
        
        return {
            "id": analysis.id,
            "user_id": analysis.user_id,
            "code_snippet": analysis.code_snippet,
            "language": analysis.language,
            "findings": analysis.findings,
            "risk_level": analysis.risk_level,
            "vulnerability_count": analysis.vulnerability_count,
            "analysis_date": analysis.analysis_date.isoformat() if analysis.analysis_date else None,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error getting analysis detail: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting analysis: {str(e)}"
        )


@router.delete("/{analysis_id}")
async def delete_analysis(
    analysis_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a specific analysis from history.
    
    User can only delete their own analyses.
    """
    # Delete analysis and verify ownership
    deleted = schemas.delete_analysis(
        db,
        user_id=current_user["user_id"],
        analysis_id=analysis_id
    )
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found or you don't have permission to delete it"
        )
    
    return {
        "message": "Analysis deleted successfully",
        "analysis_id": analysis_id
    }
