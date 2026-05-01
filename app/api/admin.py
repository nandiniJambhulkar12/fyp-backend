from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db import schemas
from app.core.auth import hash_password, create_access_token
from app.core.security import get_current_admin
import uuid

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/register")
async def register_admin(
    email: str,
    name: str,
    password: str,
    db: Session = Depends(get_db)
):
    """Register a new admin (should be protected in production)."""
    # Check if admin already exists
    existing_admin = schemas.get_admin_by_email(db, email)
    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    admin_id = str(uuid.uuid4())
    hashed_password = hash_password(password)
    
    admin = schemas.create_admin(db, email, name, hashed_password, admin_id)
    
    # Create access token
    access_token = create_access_token(data={"sub": admin_id, "role": "admin", "email": email})
    
    return {
        "message": "Admin registered successfully",
        "access_token": access_token,
        "token_type": "bearer",
        "admin": schemas.AdminResponse.from_orm(admin)
    }


@router.post("/login")
async def login_admin(
    credentials: schemas.AdminLogin,
    db: Session = Depends(get_db)
):
    """Admin login with email and password."""
    admin = schemas.get_admin_by_email(db, credentials.email)
    
    if not admin or not admin.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    from app.core.auth import verify_password
    if not verify_password(credentials.password, admin.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Create access token
    access_token = create_access_token(data={"sub": admin.id, "role": "admin", "email": admin.email})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "admin": schemas.AdminResponse.from_orm(admin)
    }


@router.get("/users")
async def get_all_users(
    current_admin: dict = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get all registered users (admin only)."""
    users = schemas.get_all_users(db)
    return {
        "users": [schemas.UserResponse.from_orm(user) for user in users]
    }


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    current_admin: dict = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get a specific user by ID (admin only)."""
    user = schemas.get_user_by_id(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return schemas.UserResponse.from_orm(user)


@router.put("/users/{user_id}/verify")
async def verify_user(
    user_id: str,
    verified: bool,
    current_admin: dict = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Approve/Reject a user (admin only)."""
    user = schemas.get_user_by_id(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user_update = schemas.UserUpdate(verified=verified)
    updated_user = schemas.update_user(db, user_id, user_update)
    
    return {
        "message": f"User {'verified' if verified else 'rejected'} successfully",
        "user": schemas.UserResponse.from_orm(updated_user)
    }


@router.put("/users/{user_id}/activate")
async def activate_user(
    user_id: str,
    active: bool,
    current_admin: dict = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Activate/Deactivate a user (admin only)."""
    user = schemas.get_user_by_id(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user_update = schemas.UserUpdate(active=active)
    updated_user = schemas.update_user(db, user_id, user_update)
    
    return {
        "message": f"User {'activated' if active else 'deactivated'} successfully",
        "user": schemas.UserResponse.from_orm(updated_user)
    }


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_admin: dict = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Delete a user (admin only)."""
    success = schemas.delete_user(db, user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {"message": "User deleted successfully"}
