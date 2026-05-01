"""Firebase authentication utilities."""

import firebase_admin
from firebase_admin import auth
from fastapi import HTTPException


def verify_firebase_token(id_token: str) -> dict:
    """Verify Firebase ID token and return decoded token."""
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Firebase token: {str(e)}")


def get_firebase_user(uid: str) -> dict:
    """Get Firebase user by UID."""
    try:
        user = auth.get_user(uid)
        return {
            "uid": user.uid,
            "email": user.email,
            "email_verified": user.email_verified,
            "display_name": user.display_name,
            "photo_url": user.photo_url,
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Firebase user not found: {str(e)}")