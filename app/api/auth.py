from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db import schemas
from app.core.auth import create_access_token
from app.core.security import get_current_user
import uuid

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
async def register_user(
    user_create: schemas.UserCreate,
    db: Session = Depends(get_db)
):
    """Register a new user (typically called after Firebase signup)."""
    # Check if user already exists
    existing_user = schemas.get_user_by_email(db, user_create.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    user_id = str(uuid.uuid4())
    user = schemas.create_user(db, user_create, user_id)
    
    # Create access token (but user won't be able to use it until verified)
    access_token = create_access_token(data={"sub": user_id, "role": "user", "email": user_create.email})
    
    return {
        "message": "User registered successfully. Please wait for admin approval.",
        "access_token": access_token,
        "token_type": "bearer",
        "user": schemas.UserResponse.from_orm(user)
    }


@router.post("/login")
async def login_user(
    payload: dict = Body(...),
    db: Session = Depends(get_db)
):
    """User login - requires Firebase authentication first."""
    email = payload.get("email")
    firebase_uid = payload.get("firebase_uid")

    if not email or not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="email and firebase_uid are required",
        )

    user = schemas.get_user_by_email(db, email)
    
    # Auto-create user if doesn't exist (for development/testing)
    if not user:
        import os
        is_dev = os.getenv("ENVIRONMENT", "development").lower() == "development"
        
        if is_dev:
            print(f"[DEV MODE] Auto-registering user: {email}")
            user_id = str(uuid.uuid4())
            user_create = schemas.UserCreate(
                email=email,
                name=email.split('@')[0],
                firebase_uid=firebase_uid
            )
            user = schemas.create_user(db, user_create, user_id)
            # Auto-verify in dev mode
            user.verified = True
            user.active = True
            db.commit()
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
    
    # In development, auto-approve unverified users
    import os
    is_dev = os.getenv("ENVIRONMENT", "development").lower() == "development"
    
    if not user.verified and not is_dev:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not verified. Please wait for admin approval."
        )
    elif not user.verified and is_dev:
        user.verified = True
        db.commit()
    
    # Verify user is active
    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account has been deactivated."
        )
    
    # Create access token
    access_token = create_access_token(data={"sub": user.id, "role": "user", "email": email})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": schemas.UserResponse.from_orm(user)
    }


@router.get("/user/profile")
async def get_user_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's profile."""
    user = schemas.get_user_by_id(db, current_user["user_id"])
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return schemas.UserResponse.from_orm(user)


@router.put("/user/profile")
async def update_user_profile(
    user_update: schemas.UserUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's profile (name, phone, etc.)."""
    user = schemas.update_user(db, current_user["user_id"], user_update)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {
        "message": "Profile updated successfully",
        "user": schemas.UserResponse.from_orm(user)
    }


@router.post("/verify-status")
async def check_verify_status(
    email: str,
    db: Session = Depends(get_db)
):
    """Check if a user is verified (for frontend polling)."""
    user = schemas.get_user_by_email(db, email)
    
    if not user:
        return {"verified": False, "active": False}
    
    return {
        "verified": user.verified,
        "active": user.active,
        "message": "User account pending" if not user.verified else "User account verified"
    }
