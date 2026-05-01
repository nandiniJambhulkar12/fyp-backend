# Admin Panel - Quick Reference Guide

## Quick Setup

### 1. Install Backend Dependencies
```bash
cd Project_UI/xai-code-auditor/backend
pip install -r requirements_updated.txt
```

### 2. Create Initial Admin Account
```python
# Create a file: create_admin.py
from app.db.database import SessionLocal
from app.db import schemas
from app.core.auth import hash_password
import uuid

db = SessionLocal()
admin_id = str(uuid.uuid4())
admin = schemas.create_admin(
    db,
    email="admin@example.com",
    name="System Administrator",
    hashed_password=hash_password("admin123"),
    admin_id=admin_id
)
print(f"✓ Admin created: {admin.email}")
```

Then run:
```bash
python create_admin.py
```

### 3. Start Backend
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Start Frontend
```bash
cd ../../../src
npm start
```

## User Routes

| Method | Endpoint | Purpose | Auth |
|--------|----------|---------|------|
| POST | `/api/auth/register` | Register new user | None |
| POST | `/api/auth/login` | User login | None |
| GET | `/api/auth/user/profile` | Get user profile | User Token |
| POST | `/api/auth/verify-status` | Check if verified | None |

## Admin Routes

| Method | Endpoint | Purpose | Auth |
|--------|----------|---------|------|
| POST | `/api/admin/register` | Create admin | None (should be protected) |
| POST | `/api/admin/login` | Admin login | None |
| GET | `/api/admin/users` | Get all users | Admin Token |
| GET | `/api/admin/users/{id}` | Get specific user | Admin Token |
| PUT | `/api/admin/users/{id}/verify` | Verify user | Admin Token |
| PUT | `/api/admin/users/{id}/activate` | Activate/Deactivate | Admin Token |
| DELETE | `/api/admin/users/{id}` | Delete user | Admin Token |

## Frontend Routes

| Route | Purpose | Protection |
|-------|---------|-----------|
| `/` | Landing page | None |
| `/login` | User login | None |
| `/signup` | User registration | None |
| `/admin-login` | Admin login | None |
| `/verification-pending` | Wait for verification | None |
| `/dashboard` | User analysis dashboard | User verified |
| `/admin-dashboard` | Admin management panel | Admin token |

## Test Scenarios

### Scenario 1: Register User, Wait for Verification, Login
```
1. Go to http://localhost:3000/signup
2. Fill form: Email: test@example.com, Name: Test User, Password: Test@123
3. Click "Create account"
→ Redirected to /verification-pending
4. Go to http://localhost:3000/admin-login
5. Login: admin@example.com / admin123
→ Redirected to /admin-dashboard
6. Click filter "Pending" 
→ See "Test User" in list
7. Click "Manage" button
8. Click "✓ Verify User"
→ User status changes to verified
9. Go back to /verification-pending page (or open new tab)
→ Auto-redirect to /login
10. Go to /login
11. Login: test@example.com / Test@123
→ Success! Redirected to /dashboard
```

### Scenario 2: Reject a User
```
1. Admin Dashboard → filter "Pending"
2. Click "Manage" on any pending user
3. Click "✗ Reject User"
→ User moved to unverified list
4. User cannot login even with correct password
```

### Scenario 3: Deactivate User
```
1. Admin Dashboard → find verified user
2. Click "Manage"
3. Click "Deactivate User"
→ User appears as "Inactive"
4. User cannot login when deactivated
```

### Scenario 4: Delete User
```
1. Admin Dashboard → find any user
2. Click "Manage"
3. Click "Delete User"
4. Confirm deletion
→ User removed from database
```

## API Examples (cURL)

### User Registration
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "name": "Test User"
  }'
```

### Admin Login
```bash
curl -X POST http://localhost:8000/api/admin/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "admin123"
  }'
```

### Get All Users (requires admin token)
```bash
curl -X GET http://localhost:8000/api/admin/users \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

### Verify User (requires admin token)
```bash
curl -X PUT "http://localhost:8000/api/admin/users/USER_ID/verify?verified=true" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

### Check Verification Status
```bash
curl -X POST http://localhost:8000/api/auth/verify-status \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com"
  }'
```

## Database Queries

### View Pending Users
```sql
SELECT id, email, name, verified, created_at FROM users WHERE verified = FALSE;
```

### View All Active Users
```sql
SELECT id, email, name, verified, active FROM users WHERE active = TRUE;
```

### Get User Registration Stats
```sql
SELECT 
  COUNT(*) as total_users,
  SUM(CASE WHEN verified THEN 1 ELSE 0 END) as verified_count,
  SUM(CASE WHEN NOT verified THEN 1 ELSE 0 END) as pending_count;
FROM users;
```

## Admin Dashboard Features

### Tabs/Filters
- **All Users**: Shows all registered users
- **Verified**: Shows only verified users
- **Pending**: Shows only users waiting for approval

### User Management
- Click "Manage" button on any user
- Modal appears with options:
  - **Verify User**: Approve the user
  - **Reject User**: Unapprove the user
  - **Activate/Deactivate**: Toggle user access
  - **Delete User**: Permanently remove account

### Statistics
- **Total Users**: Count of all registered users
- **Verified**: Count of approved users
- **Pending**: Count of awaiting approval
- **Active**: Count of active accounts

## Key Database Fields

### Users Table
```
id                UUID (primary key)
email             VARCHAR (unique)
name              VARCHAR
verified          BOOLEAN (default: false)
active            BOOLEAN (default: true)
role              VARCHAR (default: 'user')
created_at        DATETIME
updated_at        DATETIME
```

### Admins Table
```
id                UUID (primary key)
email             VARCHAR (unique)
name              VARCHAR
hashed_password   VARCHAR
active            BOOLEAN (default: true)
created_at        DATETIME
```

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| 401 Unauthorized on admin routes | Check token is expired or invalid. Tokens last 30 minutes. |
| "User not found" | User wasn't registered in backend. Check database. |
| "User account is not verified" | Only happens after user signup. Admin must verify first. |
| Admin can't login | Verify admin account exists in database. Check password is correct. |
| Frontend can't connect to backend | Ensure backend is running on port 8000. Check CORS settings. |

## Token Expiry
- Access tokens expire after **30 minutes**
- User will be redirected to login page on expiry
- Admin needs to login again to continue managing users

## Important Notes

1. **Modification Required**: Create initial admin before allowing users to register
2. **Verification Flow**: All new users start with `verified=False`
3. **Login Block**: Unverified users cannot login even with correct password
4. **Admin Only**: Only admins can access verification endpoints
5. **Password Security**: Admin passwords are bcrypt hashed
6. **No Email System**: Currently doesn't send email notifications (can be added)

## Frontend Components Used

- **AdminLogin.tsx**: Admin login page
- **AdminDashboard.tsx**: Admin management interface
- **AdminRoute.tsx**: Protected route component
- **VerificationPending.tsx**: Pending verification page
- **Login.tsx**: Updated with backend integration
- **Signup.tsx**: Updated with backend registration

## Next Steps

After setup, consider implementing:
1. Email notifications for new signups
2. Admin email notifications
3. Audit logs for all admin actions
4. Custom admin roles with granular permissions
5. User activity tracking
