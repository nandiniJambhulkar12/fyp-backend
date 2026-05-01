# 🔐 User Verification System - Complete Guide

## Overview

The authentication system ensures that:
- ✅ New users start with `verified=False`
- ✅ Only admins can verify users
- ✅ Unverified users see: **"Your account is pending admin approval."**
- ✅ Only verified users access protected routes (code analysis, reports)

---

## 🔄 User Verification Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                      REGISTRATION PHASE                         │
│                                                                   │
│  User Signup (Firebase) → Backend Registration (verified=False)  │
│                                ↓                                  │
│                  Display: "Pending admin approval"               │
│                                ↓                                  │
│               Frontend auto-polls every 5 seconds                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    ADMIN VERIFICATION PHASE                      │
│                                                                   │
│  Admin Dashboard → View Pending Users → Click "Verify"          │
│                                ↓                                  │
│        Backend: PUT /api/admin/users/{id}/verify?verified=true   │
│                                ↓                                  │
│           Database: User.verified changed to True               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      LOGIN VERIFICATION PHASE                    │
│                                                                   │
│  Unverified User Tries Login:                                   │
│  POST /api/auth/login                                            │
│           ↓                                                       │
│  Backend checks: if not user.verified:                          │
│  Return: 403 "Your account is pending admin approval."          │
│                                                                   │
│  Verified User Tries Login:                                     │
│  POST /api/auth/login                                            │
│           ↓                                                       │
│  Backend checks: ✓ verified=True ✓ active=True                 │
│  Return: JWT Token + Access to Dashboard                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📧 Error Messages

### User Not Verified (403 Forbidden)
```json
{
  "detail": "Your account is pending admin approval."
}
```
**When**: User tries to login before admin verification

### User Deactivated (403 Forbidden)
```json
{
  "detail": "Your account has been deactivated. Please contact admin."
}
```
**When**: Admin deactivated user account

### Invalid Token (401 Unauthorized)
```json
{
  "detail": "Invalid authentication credentials"
}
```
**When**: Token expired or invalid

### User Not Found (401 Unauthorized)
```json
{
  "detail": "User not found"
}
```
**When**: User ID in token doesn't exist in database

---

## 🛡️ Protected Routes

### User Protected Routes (Requires Verification)

#### 1. Code Analysis Endpoint
```
POST /api/analyze
Security: Requires verified user token
Parameters:
  - file: Optional file upload
  - code: Code text
  - language: Programming language

Middleware Chain:
  1. get_current_user() → Validates token
  2. Checks: user.verified == True
  3. Checks: user.active == True
  4. If OK → Process analysis
  5. If NOT → Return 403 error
```

**Frontend Usage:**
```typescript
const analyzeCode = async (code: string) => {
  try {
    const response = await axios.post('http://localhost:8000/api/analyze', 
      { code },
      { headers: { Authorization: `Bearer ${userToken}` } }
    );
    return response.data;
  } catch (error) {
    if (error.response?.status === 403) {
      console.error(error.response.data.detail);
      // Show: "Your account is pending admin approval."
    }
  }
};
```

#### 2. Get Report Endpoint
```
GET /api/reports/{report_id}
Security: Requires verified user token
Response:
  - 200: Report data (if verified)
  - 403: User not verified
  - 404: Report not found

Middleware Chain:
  1. get_current_user() → Validates token
  2. Checks: user.verified == True
  3. Checks: user.active == True
  4. If OK → Return report
  5. If NOT → Return 403 error
```

#### 3. Get User Profile
```
GET /api/auth/user/profile
Security: Requires verified user token
Response: User profile (email, name, verified status, etc.)
```

---

## 🔑 Backend Middleware Details

### get_current_user() Middleware

**File**: `app/core/security.py`

**Flow**:
```python
1. Extract JWT token from request header
2. Verify token validity (not expired, correct signature)
3. Extract user_id from token
4. Query database for user
5. Check: user exists?
   → If NO: Return 401 "User not found"
   → If YES: Continue
6. Check: user.verified == True?
   → If NO: Return 403 "Your account is pending admin approval."
   → If YES: Continue
7. Check: user.active == True?
   → If NO: Return 403 "Your account has been deactivated."
   → If YES: Continue
8. Return user info to route handler
```

**Code Structure**:
```python
async def get_current_user(credentials: HTTPAuthCredentials) -> dict:
    # 1. Get token
    token = credentials.credentials
    
    # 2. Verify token
    payload = verify_token(token)
    if not payload:
        raise 401 Unauthorized
    
    # 3. Get user from DB
    user = schemas.get_user_by_id(db, user_id)
    if not user:
        raise 401 User not found
    
    # 4. Check verified ⚠️ CRITICAL
    if not user.verified:
        raise 403 "Your account is pending admin approval."
    
    # 5. Check active
    if not user.active:
        raise 403 "Account deactivated"
    
    # 6. Return authenticated user
    return {...}
```

---

## 🚀 Implementation Checklist

### Backend Setup
- [x] User model has `verified` field (default=False)
- [x] User model has `active` field (default=True)
- [x] Registration sets verified=False
- [x] Authentication middleware checks verified status
- [x] Login endpoint rejects unverified users
- [x] Protected routes use get_current_user middleware
- [x] Error messages are clear and helpful
- [x] Logging for security events

### Frontend Setup
- [x] Signup shows "pending approval" message
- [x] VerificationPending page with auto-polling
- [x] Login shows error message if not verified
- [x] Dashboard protected by PrivateRoute
- [x] Auto-redirect when verified

### Admin Features
- [x] Admin can view pending users
- [x] Admin can verify users
- [x] Admin can reject users
- [x] Admin can deactivate users
- [x] Admin can delete users

---

## 📊 Database State Examples

### Newly Registered User
```sql
SELECT id, email, verified, active FROM users WHERE email='new@example.com';

┌──────────────────────────────┬──────────────────┬──────────┬────────┐
│ id                           │ email            │ verified │ active │
├──────────────────────────────┼──────────────────┼──────────┼────────┤
│ 550e8400-e29b-41d4-a716... │ new@example.com  │ false    │ true   │
└──────────────────────────────┴──────────────────┴──────────┴────────┘
```

### Admin Verified the User
```sql
UPDATE users SET verified=true WHERE email='new@example.com';

┌──────────────────────────────┬──────────────────┬──────────┬────────┐
│ id                           │ email            │ verified │ active │
├──────────────────────────────┼──────────────────┼──────────┼────────┤
│ 550e8400-e29b-41d4-a716... │ new@example.com  │ true     │ true   │
└──────────────────────────────┴──────────────────┴──────────┴────────┘
```

### Admin Rejected/Deactivated User
```sql
UPDATE users SET verified=false WHERE email='rejected@example.com';

┌──────────────────────────────┬──────────────────┬──────────┬────────┐
│ id                           │ email            │ verified │ active │
├──────────────────────────────┼──────────────────┼──────────┼────────┤
│ 550e8400-e29b-41d4-a717... │ rejected@ex.com  │ false    │ true   │
└──────────────────────────────┴──────────────────┴──────────┴────────┘
```

---

## 🧪 Testing Verification Flow

### Test Case 1: Unverified User Cannot Analyze Code

```bash
# 1. Register user
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","name":"Test User"}'

Response:
{
  "message": "User registered successfully. Please wait for admin approval.",
  "access_token": "eyJhbGc...",
  "user": {"verified": false, ...}
}

# 2. Save token: TOKEN="eyJhbGc..."

# 3. Try to analyze without verification
curl -X POST http://localhost:8000/api/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'code=print("hello")'

Response (403):
{
  "detail": "Your account is pending admin approval."
}

✓ PASS: Unverified user blocked
```

### Test Case 2: Admin Verifies User, Now Can Analyze

```bash
# 1. (From admin) Verify the user
curl -X PUT "http://localhost:8000/api/admin/users/USER_ID/verify?verified=true" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

Response:
{
  "message": "User verified successfully",
  "user": {"verified": true, ...}
}

# 2. Now try analysis again
curl -X POST http://localhost:8000/api/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'code=print("hello")'

Response (200):
{
  "findings": [...],
  "summary": {...}
}

✓ PASS: Verified user can analyze
```

### Test Case 3: Admin Deactivates User

```bash
# 1. Deactivate user
curl -X PUT "http://localhost:8000/api/admin/users/USER_ID/activate?active=false" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

Response:
{
  "message": "User deactivated successfully",
  "user": {"active": false, ...}
}

# 2. Try to analyze
curl -X POST http://localhost:8000/api/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -d 'code=print("hello")'

Response (403):
{
  "detail": "Your account has been deactivated. Please contact admin."
}

✓ PASS: Deactivated user blocked
```

---

## 🔍 Logging & Monitoring

### Security Events Logged

**File**: Check backend logs with messages like:

```
⚠️ [WARNING] Unverified user 550e8400-e29b-41d4-a716 (test@example.com) 
           attempted to access protected route

⚠️ [WARNING] Deactivated user 550e8400-e29b-41d4-a717 (inactive@example.com) 
            attempted to access protected route

⚠️ [WARNING] Invalid token provided for user endpoint

⚠️ [WARNING] Non-admin user 550e8400-e29b-41d4-a718 tried to access 
            admin endpoint
```

### Enable Logging

Add to backend configuration:
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

---

## 📝 API Response Codes

| Code | Scenario | Message |
|------|----------|---------|
| 200 | Success | Data returned |
| 400 | Bad request | Invalid parameters |
| 401 | Token invalid | "Invalid authentication credentials" |
| 401 | User not found | "User not found" |
| 403 | Not verified | "Your account is pending admin approval." |
| 403 | Deactivated | "Your account has been deactivated." |
| 403 | Not admin | "Insufficient permissions - Admin role required" |
| 404 | Resource not found | "Report not found" |

---

## 🚨 Troubleshooting

### Issue: "User account is not verified. Please wait for admin approval."

**Cause**: User is not verified yet
**Solution**: 
1. Ask admin to verify in admin dashboard
2. Wait for verification
3. Login again

### Issue: "Your account has been deactivated."

**Cause**: Admin deactivated the account
**Solution**: Contact admin to reactivate

### Issue: "Invalid authentication credentials"

**Cause**: Token expired or invalid
**Solution**:
1. Clear localStorage
2. Login again
3. Get new token

### Issue: Protected route returns 401

**Cause**: Missing or malformed token
**Solution**:
1. Check Authorization header format: `Bearer TOKEN`
2. Verify token is not expired
3. Login again if needed

---

## 🔐 Security Best Practices

### ✅ DO:
- ✅ Always use HTTPS in production
- ✅ Store tokens securely (httpOnly cookies recommended)
- ✅ Verify tokens on every protected request
- ✅ Log security events
- ✅ Use strong admin passwords
- ✅ Rotate secrets regularly

### ❌ DON'T:
- ❌ Store tokens in localStorage for sensitive data (use httpOnly)
- ❌ Skip verification checks
- ❌ Log sensitive user data
- ❌ Share SECRET_KEY between environments
- ❌ Allow unverified users to access features

---

## 🎯 Summary

| Component | Status | Details |
|-----------|--------|---------|
| Registration | ✅ Complete | verified=False by default |
| Verification | ✅ Complete | Admin must approve |
| Error Messages | ✅ Complete | Clear and actionable |
| Protected Routes | ✅ Complete | All analysis/report routes secured |
| Middleware | ✅ Complete | get_current_user validates all checks |
| Frontend Integration | ✅ Complete | Shows pending message, blocks access |
| Logging | ✅ Complete | Security events logged |
| Testing | ✅ Complete | All scenarios covered |

---

**Status**: ✅ **VERIFICATION SYSTEM COMPLETE AND TESTED**

All users must be verified by an admin before accessing protected features.
