# ✅ Verification System - Testing Guide

## Quick Test Scenarios

### Scenario 1: Unverified User Cannot Access Code Analysis

#### Step 1: Register New User
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "unverified@test.com",
    "name": "Unverified User"
  }'
```

**Expected Response**:
```json
{
  "message": "User registered successfully. Please wait for admin approval.",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "unverified@test.com",
    "name": "Unverified User",
    "verified": false,  ← NOTE: false
    "active": true,
    "role": "user",
    "created_at": "2026-02-16T10:30:00",
    "updated_at": "2026-02-16T10:30:00"
  }
}
```

#### Step 2: Try to Analyze Code (Without Verification)
```bash
# Save the token first
TOKEN="<access_token_from_above>"

# Try to analyze
curl -X POST http://localhost:8000/api/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'code=print("hello world")&language=python'
```

**Expected Response** (403 Forbidden):
```json
{
  "detail": "Your account is pending admin approval."
}
```

✅ **PASS**: Unverified user is blocked from analyzing code

---

### Scenario 2: Admin Verifies User, Then Can Access

#### Step 1: Admin Logs In
```bash
curl -X POST http://localhost:8000/api/admin/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "admin123"
  }'
```

**Expected Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "admin": {
    "id": "admin-uuid",
    "email": "admin@example.com",
    "name": "System Administrator",
    "created_at": "2026-02-16T10:00:00"
  }
}
```

#### Step 2: View Pending Users
```bash
ADMIN_TOKEN="<admin_access_token>"
USER_ID="550e8400-e29b-41d4-a716-446655440000"

curl -X GET http://localhost:8000/api/admin/users \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Expected Response** (partial):
```json
{
  "users": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "email": "unverified@test.com",
      "verified": false,  ← Still unverified
      "active": true,
      ...
    }
  ]
}
```

#### Step 3: Admin Verifies User
```bash
curl -X PUT "http://localhost:8000/api/admin/users/$USER_ID/verify?verified=true" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Expected Response**:
```json
{
  "message": "User verified successfully",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "unverified@test.com",
    "verified": true,  ← NOW TRUE!
    "active": true,
    ...
  }
}
```

#### Step 4: User Can Now Analyze
```bash
TOKEN="<user_access_token_from_step_1>"

curl -X POST http://localhost:8000/api/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'code=print("hello world")&language=python'
```

**Expected Response** (200 OK):
```json
{
  "findings": [
    {
      "id": "finding-1",
      "rule_id": "RULE-001",
      "severity": "Low",
      ...
    }
  ],
  "summary": {...}
}
```

✅ **PASS**: After verification, user can access protected routes

---

### Scenario 3: Admin Rejects User

#### Step 1: Admin Rejects (Sets verified=False)
```bash
ADMIN_TOKEN="<admin_token>"
USER_ID="550e8400-e29b-41d4-a716-446655440000"

curl -X PUT "http://localhost:8000/api/admin/users/$USER_ID/verify?verified=false" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Expected Response**:
```json
{
  "message": "User rejected successfully",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "verified": false,  ← Rejected
    ...
  }
}
```

#### Step 2: User Cannot Access
```bash
TOKEN="<user_access_token>"

curl -X POST http://localhost:8000/api/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -d 'code=print("hello")'
```

**Expected Response** (403):
```json
{
  "detail": "Your account is pending admin approval."
}
```

✅ **PASS**: Rejected user is blocked again

---

### Scenario 4: Admin Deactivates User

#### Step 1: Admin Deactivates
```bash
ADMIN_TOKEN="<admin_token>"
USER_ID="550e8400-e29b-41d4-a716-446655440000"

curl -X PUT "http://localhost:8000/api/admin/users/$USER_ID/activate?active=false" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Expected Response**:
```json
{
  "message": "User deactivated successfully",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "verified": true,
    "active": false,  ← Deactivated!
    ...
  }
}
```

#### Step 2: Even Verified User Cannot Access
```bash
TOKEN="<user_access_token>"

curl -X POST http://localhost:8000/api/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -d 'code=print("hello")'
```

**Expected Response** (403):
```json
{
  "detail": "Your account has been deactivated. Please contact admin."
}
```

✅ **PASS**: Deactivated users are blocked

---

## Frontend Testing

### Test 1: Registration Flow
```typescript
// 1. User clicks "Sign up"
// 2. Fills form with email/password
// 3. Clicks "Create account"

// Expected:
// ✓ Firebase account created
// ✓ Backend user registered with verified=false
// ✓ Redirected to VerificationPending page
// ✓ See message: "Your account is pending admin approval"
```

### Test 2: Check Verification Status
```typescript
// VerificationPending.tsx:
// 1. Page auto-polls every 5 seconds
// 2. Calls GET /api/auth/verify-status
// 3. While unverified: Shows "Waiting..." message
// 4. When admin verifies: Auto-redirects to /login

// Expected:
// ✓ Auto-polls working
// ✓ Last checked time updates
// ✓ Manual "Check Now" button works
// ✓ Auto-redirect on verification
```

### Test 3: Login Verification Check
```typescript
// Login.tsx:
// 1. User enters email/password
// 2. Firebase authenticates
// 3. Calls POST /api/auth/login
// 4. Backend checks: verified & active

// Expected responses:
// ✓ Unverified: 403 "Your account is pending admin approval."
// ✓ Deactivated: 403 "Your account has been deactivated."
// ✓ Verified+Active: 200 + token + redirect to dashboard
```

### Test 4: Protected Dashboard Access
```typescript
// Dashboard.tsx (protected by PrivateRoute):
// 1. User tries to access /dashboard
// 2. PrivateRoute checks for token
// 3. Token sent with analyze request

// Expected:
// ✓ Unverified users redirected to /login
// ✓ Verified users see dashboard
// ✓ Analysis requests work only if verified
```

---

## Database Verification

### Check User Status
```sql
-- View pending users (not verified)
SELECT email, name, verified, active, created_at 
FROM users 
WHERE verified = FALSE;

-- View approved users
SELECT email, name, verified, active 
FROM users 
WHERE verified = TRUE;

-- Count statistics
SELECT 
  COUNT(*) as total,
  SUM(CASE WHEN verified THEN 1 ELSE 0 END) as approved,
  SUM(CASE WHEN NOT verified THEN 1 ELSE 0 END) as pending
FROM users;
```

---

## Error Message Verification

### Messages to Expect

| Endpoint | Status | Message | Scenario |
|----------|--------|---------|----------|
| POST /analyze | 403 | "Your account is pending admin approval." | Unverified user |
| POST /analyze | 403 | "Your account has been deactivated." | Deactivated user |
| GET /reports/{id} | 403 | "Your account is pending admin approval." | Unverified user |
| POST /auth/login | 403 | "User account is not verified. Please wait for admin approval." | Unverified login attempt |

---

## Postman Collection

### Collection Name: `Verification System Tests`

**Requests**:

1. **Register User**
   - Method: POST
   - URL: `{{base_url}}/api/auth/register`
   - Body: `{"email":"test@example.com","name":"Test"}`

2. **Unverified User Analyze**
   - Method: POST
   - URL: `{{base_url}}/api/analyze`
   - Headers: `Authorization: Bearer {{user_token}}`
   - Body: `code=print("hello")`

3. **Admin Login**
   - Method: POST
   - URL: `{{base_url}}/api/admin/login`
   - Body: `{"email":"admin@example.com","password":"admin123"}`

4. **Verify User**
   - Method: PUT
   - URL: `{{base_url}}/api/admin/users/{{user_id}}/verify?verified=true`
   - Headers: `Authorization: Bearer {{admin_token}}`

5. **Verified User Analyze**
   - Method: POST
   - URL: `{{base_url}}/api/analyze`
   - Headers: `Authorization: Bearer {{user_token}}`
   - Body: `code=print("hello")`

6. **Check Verification Status**
   - Method: POST
   - URL: `{{base_url}}/api/auth/verify-status`
   - Body: `{"email":"test@example.com"}`

---

## Debugging Checklist

- [ ] Backend logs show user registration with verified=false
- [ ] Admin can see unverified users in dashboard
- [ ] Admin verify action updates DB
- [ ] API returns correct error messages
- [ ] Frontend shows pending messages
- [ ] Auto-polling works every 5 seconds
- [ ] After verification, user can login
- [ ] After verified, user can analyze code
- [ ] Deactivated users are blocked
- [ ] All HTTP status codes are correct

---

## Common Issues & Fixes

### Issue: User can access analysis without verification

**Debug Steps**:
1. Check `app/api/analyze.py` has `get_current_user` dependency
2. Check middleware is checking `user.verified`
3. Check database has `verified` column
4. Restart backend after code changes

### Issue: Error message not showing to user

**Debug Steps**:
1. Check frontend is reading `error.response.data.detail`
2. Check backend is returning proper JSON response
3. Check CORS headers allow error responses
4. Check browser console for errors

### Issue: User token exists but still blocked

**Debug Steps**:
1. Check token has correct `sub` (user_id)
2. Check user exists in database
3. Check `user.verified` is actually False in DB
4. Check no typos in error messages

---

## Performance Testing

### Load Test: 1000 Concurrent Unverified Users

```bash
# Apache Bench test
ab -n 1000 -c 100 \
  -H "Authorization: Bearer TOKEN" \
  -p analyze_payload.json \
  http://localhost:8000/api/analyze
```

**Expected Results**:
- ✓ All requests blocked (403)
- ✓ Response time < 100ms
- ✓ No database crashes

---

## Success Criteria ✅

- [ ] Unverified users cannot access `/api/analyze`
- [ ] Unverified users cannot access `/api/reports/*`
- [ ] Error message shows "Your account is pending admin approval."
- [ ] Admin can verify users
- [ ] After verification, user can access routes
- [ ] Deactivated users are blocked even if verified
- [ ] Frontend shows correct messages
- [ ] Database reflects changes correctly
- [ ] All error codes are 403 Forbidden
- [ ] Logging shows security events

---

**Status**: ✅ **READY FOR TESTING**

All verification system components are implemented and ready to test.
