from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer
from typing import Optional, Tuple
from app.core.auth import verify_token
from app.db.database import SessionLocal
from app.db import schemas
import logging

# Setup logging
logger = logging.getLogger(__name__)

security = HTTPBearer()


class HTTPAuthCredentials:
    """Simple credential holder for Bearer token"""
    def __init__(self, scheme: str, credentials: str):
        self.scheme = scheme
        self.credentials = credentials


async def get_token_from_header(credentials: Optional[Tuple] = Depends(security)) -> str:
    """Extract token from Bearer header"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )
    return credentials.credentials if hasattr(credentials, 'credentials') else str(credentials)


async def get_current_admin(token: str = Depends(get_token_from_header)) -> dict:
    """
    Verify admin authentication and role.
    
    Raises:
        401: Invalid or expired token
        403: Not an admin
    """
    payload = verify_token(token)
    
    if not payload:
        logger.warning("Invalid token provided for admin endpoint")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    
    admin_id = payload.get("sub")
    role = payload.get("role")
    
    if role != "admin":
        logger.warning(f"Non-admin user {admin_id} tried to access admin endpoint")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions - Admin role required",
        )
    
    db = SessionLocal()
    try:
        admin = schemas.get_admin_by_id(db, admin_id)
        
        if not admin:
            logger.warning(f"Admin {admin_id} not found in database")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Admin not found",
            )
        
        if not admin.active:
            logger.warning(f"Admin {admin_id} is inactive")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin account is deactivated.",
            )
        
        return {"admin_id": admin_id, "role": role, "email": admin.email}
    finally:
        db.close()


async def get_current_user(token: str = Depends(get_token_from_header)) -> dict:
    """
    Verify user authentication and verification status.
    
    Checks:
        1. Token validity
        2. User exists in database
        3. User is verified
        4. User is active
    
    Raises:
        401: Invalid token or user not found
        403: User not verified or account deactivated
    """
    payload = verify_token(token)
    
    if not payload:
        logger.warning("Invalid token provided for user endpoint")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    
    user_id = payload.get("sub")
    role = payload.get("role")
    
    db = SessionLocal()
    try:
        user = schemas.get_user_by_id(db, user_id)
        
        if not user:
            logger.warning(f"User {user_id} not found in database")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        
        # ⚠️ CRITICAL: Check user is verified
        if not user.verified:
            logger.info(f"Unverified user {user_id} ({user.email}) attempted to access protected route")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is pending admin approval.",
            )
        
        # Check if user is active
        if not user.active:
            logger.warning(f"Deactivated user {user_id} ({user.email}) attempted to access protected route")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been deactivated. Please contact admin.",
            )
        
        return {"user_id": user_id, "role": role, "email": user.email}
    finally:
        db.close()


async def optional_auth(credentials: Optional[Tuple] = Depends(security)) -> dict:
    """
    Optional authentication - returns user/admin if token is valid.
    Does not require verification.
    """
    if not credentials:
        return {"authenticated": False}
    
    token = credentials.credentials if hasattr(credentials, 'credentials') else str(credentials)
    payload = verify_token(token)
    
    if not payload:
        return {"authenticated": False}
    
    return {"authenticated": True, "sub": payload.get("sub"), "role": payload.get("role")}


async def verify_user_ownership(user_id: str, current_user: dict) -> bool:
    """
    Verify that the current user owns the resource.
    
    Returns:
        True if user is accessing their own resource
        False otherwise
    """
    return current_user["user_id"] == user_id


async def verify_admin_or_owner(user_id: str, current_user: dict) -> bool:
    """
    Check if user is admin OR owns the resource.
    """
    if current_user["role"] == "admin":
        return True
    return current_user["user_id"] == user_id
