from functools import lru_cache

from fastapi import APIRouter, Depends, Header, HTTPException

from config import get_settings
from models import (
    AuthLoginRequest,
    AuthRegisterRequest,
    ProfileUpdateRequest,
    TokenResponse,
    UserProfile,
    VerifyStatusRequest,
)
from utils.local_store import LocalJSONStore
from utils.token_manager import TokenManager


router = APIRouter(prefix="/auth")


@lru_cache(maxsize=1)
def get_store() -> LocalJSONStore:
    settings = get_settings()
    return LocalJSONStore(settings.users_path, settings.history_path)


@lru_cache(maxsize=1)
def get_token_manager() -> TokenManager:
    return TokenManager(get_settings().secret_key)


def get_current_user(authorization: str = Header(default="")) -> UserProfile:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = get_token_manager().verify_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication token") from exc

    email = payload.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    user = get_store().get_user(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/register")
async def register_user(payload: AuthRegisterRequest):
    user = get_store().register_user(email=payload.email, name=payload.name)
    return {
        "message": "User registered successfully",
        "user": user.dict(),
    }


@router.post("/login", response_model=TokenResponse)
async def login_user(payload: AuthLoginRequest):
    user = get_store().register_user(
        email=payload.email,
        name=payload.email.split("@")[0],
        firebase_uid=payload.firebase_uid,
    )
    if not user.active:
        raise HTTPException(status_code=403, detail="Account is inactive")
    if not user.verified:
        raise HTTPException(status_code=403, detail="User not verified or account issue")

    access_token = get_token_manager().issue_token({"email": user.email, "sub": user.id})
    return TokenResponse(access_token=access_token)


@router.post("/verify-status")
async def verify_status(payload: VerifyStatusRequest):
    user = get_store().get_user(payload.email)
    if not user:
        return {"verified": False, "active": False}
    return {"verified": user.verified, "active": user.active}


@router.get("/user/profile", response_model=UserProfile)
async def get_user_profile(current_user: UserProfile = Depends(get_current_user)):
    return current_user


@router.put("/user/profile")
async def update_user_profile(
    payload: ProfileUpdateRequest,
    current_user: UserProfile = Depends(get_current_user),
):
    user = get_store().update_user(
        email=current_user.email,
        name=payload.name,
        phone=payload.phone,
    )
    return {"message": "Profile updated successfully", "user": user.dict()}