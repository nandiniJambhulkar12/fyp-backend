# Admin Panel Implementation Guide

## Overview
A complete admin panel system has been implemented with role-based access control, user verification, and administrative functions.

## Key Features Implemented

### 1. **Database Schema Changes**
- **User Model**: Added `verified` and `active` fields to track user status
- **Admin Model**: Separate admin accounts with hashed passwords
- **Fields Added**:
  - `verified`: Boolean flag (default: False) - user must be verified to use platform
  - `active`: Boolean flag (default: True) - admin can deactivate users
  - `role`: String field ('user' or 'admin')
  - Timestamps: `created_at` and `updated_at`

### 2. **Backend API Routes**

#### Authentication Routes (`/api/auth`)
```
POST   /api/auth/register           - Register new user
POST   /api/auth/login              - User login with verification check
GET    /api/auth/user/profile       - Get current user profile
POST   /api/auth/verify-status      - Check user verification status
```

#### Admin Routes (`/api/admin`)
```
POST   /api/admin/register          - Create new admin (protected)
POST   /api/admin/login             - Admin login with password
GET    /api/admin/users             - Get all users (admin only)
GET    /api/admin/users/{user_id}   - Get specific user (admin only)
PUT    /api/admin/users/{user_id}/verify   - Approve/Reject user
PUT    /api/admin/users/{user_id}/activate - Activate/Deactivate user
DELETE /api/admin/users/{user_id}   - Delete user account
```

### 3. **Authentication & Security**

#### JWT Token Implementation
- **Location**: `app/core/auth.py`
- **Features**:
  - Password hashing with bcrypt
  - JWT token generation and validation
  - Token expiry: 30 minutes
  - Secret key configuration via environment variable

#### Role-Based Access Control (RBAC)
- **Location**: `app/core/security.py`
- **Middleware Functions**:
  - `get_current_admin()` - Verifies admin token and role
  - `get_current_user()` - Verifies user token and verified status
  - `optional_auth()` - Optional authentication
  
- **Restrictions**:
  - Users must be verified to access dashboard
  - Users must be active to use analysis features
  - Admins can only access admin routes

### 4. **Frontend Components**

#### AdminLogin Component
- **Path**: `src/components/AdminLogin.tsx`
- **Features**:
  - Secure email/password login
  - Error handling
  - Token storage in localStorage
  - Redirect to admin dashboard on success

#### AdminDashboard Component
- **Path**: `src/components/AdminDashboard.tsx`
- **Features**:
  - List all users with pagination
  - Filter users by verification status (All/Verified/Pending)
  - Real-time statistics (Total, Verified, Pending, Active)
  - User management modal with actions:
    - ✓ Verify User
    - ✗ Reject User
    - Activate/Deactivate User
    - Delete User
  - Responsive dark theme design

#### AdminRoute Component
- **Path**: `src/components/AdminRoute.tsx`
- **Features**:
  - Protected route for admin pages
  - Checks admin token validity
  - Redirects unauthenticated users to admin login

#### VerificationPending Component
- **Path**: `src/components/VerificationPending.tsx`
- **Features**:
  - Shows after user signup
  - Polls verification status every 5 seconds
  - Auto-redirects to login when verified
  - Manual check button available

### 5. **Updated Components**

#### Signup Component
- Now registers users with backend after Firebase signup
- Redirects to `VerificationPending` page instead of dashboard
- Shows verification pending message to users

#### Login Component
- Integrated backend login verification
- Checks if user is verified before allowing access
- Stores backend JWT token in localStorage
- Added "Admin Login" link

#### App.tsx
- New routes added:
  - `/admin-login` - Admin login page
  - `/admin-dashboard` - Admin dashboard (protected)
  - `/verification-pending` - Pending verification page

## Database Schema

### Users Table
```sql
CREATE TABLE users (
    id VARCHAR PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    name VARCHAR NOT NULL,
    verified BOOLEAN DEFAULT FALSE,
    active BOOLEAN DEFAULT TRUE,
    role VARCHAR DEFAULT 'user',
    created_at DATETIME DEFAULT NOW(),
    updated_at DATETIME DEFAULT NOW()
);
```

### Admins Table
```sql
CREATE TABLE admins (
    id VARCHAR PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    name VARCHAR NOT NULL,
    hashed_password VARCHAR NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT NOW()
);
```

## User Flow Diagram

### Regular User Flow
```
1. User visits app
   ↓
2. User clicks "Sign up"
   ↓
3. Enter email/password/name (Firebase signup)
   ↓
4. Backend registers user (verified=False)
   ↓
5. Redirected to VerificationPending page
   ↓
6. Admin reviews and verifies user
   ↓
7. User checks status (auto-polls every 5 seconds)
   ↓
8. User can now login
   ↓
9. Backend validates verified=True
   ↓
10. User can access dashboard
```

### Admin Flow
```
1. Admin visits /admin-login
   ↓
2. Enter email/password
   ↓
3. Backend validates credentials
   ↓
4. JWT token returned
   ↓
5. Redirected to /admin-dashboard
   ↓
6. View all users
   ↓
7. Filter by status (All/Verified/Pending)
   ↓
8. Click "Manage" to verify/reject/activate/delete users
```

## Environment Variables

**Backend (.env)**
```
SECRET_KEY=your-secret-key-change-this-in-production
DATABASE_URL=sqlite:///./xai_auditor.db
```

**Frontend (.env)**
```
REACT_APP_API_URL=http://localhost:8000
REACT_APP_FIREBASE_CONFIG=your-firebase-config
```

## New Dependencies Added

### Backend (requirements.txt)
```
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
bcrypt==4.0.1
```

### Frontend
- Uses existing axios for API calls
- No new dependencies needed

## Setup Instructions

### 1. Backend Setup
```bash
cd Project_UI/xai-code-auditor/backend
pip install -r requirements_updated.txt
python app/main.py
```

### 2. Frontend Setup
```bash
cd Project_UI
npm install
npm start
```

### 3. Create Initial Admin
```python
# Run this script in Python to create initial admin
from app.db.database import SessionLocal
from app.db import schemas
from app.core.auth import hash_password
import uuid

db = SessionLocal()
admin_id = str(uuid.uuid4())
admin = schemas.create_admin(
    db,
    email="admin@example.com",
    name="Admin User",
    hashed_password=hash_password("admin123"),
    admin_id=admin_id
)
print(f"Admin created: {admin.email}")
```

## Testing Workflow

### 1. User Registration & Verification
```
1. Go to /signup
2. Register with email/password (Firebase)
3. Redirected to /verification-pending
4. Go to /admin-login
5. Login as admin (use credentials from initial admin creation)
6. View pending users
7. Click "Manage"
8. Click "✓ Verify User"
9. Go back to /verification-pending
10. Should redirect to /login after verification
11. User can now login and access dashboard
```

### 2. User Management
```
1. Admin can:
   - View all users with filters
   - Approve/Reject users
   - Activate/Deactivate users
   - Delete user accounts
2. Changes are reflected immediately
```

### 3. User Cannot Access Without Verification
```
1. User tries to directly access /dashboard without verification
2. Login page redirects to /verification-pending if not verified
```

## API Response Examples

### User Registration
```json
{
  "message": "User registered successfully. Please wait for admin approval.",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "John Doe",
    "verified": false,
    "active": true,
    "role": "user",
    "created_at": "2024-02-16T10:30:00",
    "updated_at": "2024-02-16T10:30:00"
  }
}
```

### Admin Login
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "admin": {
    "id": "uuid",
    "email": "admin@example.com",
    "name": "Admin User",
    "created_at": "2024-02-16T10:00:00"
  }
}
```

### Get All Users
```json
{
  "users": [
    {
      "id": "uuid",
      "email": "user@example.com",
      "name": "John Doe",
      "verified": true,
      "active": true,
      "role": "user",
      "created_at": "2024-02-16T10:30:00",
      "updated_at": "2024-02-16T10:35:00"
    }
  ]
}
```

## Security Considerations

1. **Token Storage**: Access tokens stored in localStorage (consider httpOnly cookies for production)
2. **HTTPS**: Use HTTPS in production
3. **Password Hashing**: Bcrypt with salt rounds
4. **Admin Endpoint Protection**: All admin endpoints require valid admin JWT
5. **User Verification**: Users cannot bypass verification without admin approval
6. **Role-Based Access**: Strict role checking in middleware

## Future Enhancements

1. **Email Notifications**: Send verification emails to users
2. **Admin Notifications**: Notify admins of new signups
3. **Audit Logs**: Track all admin actions
4. **Two-Factor Authentication**: Add 2FA for admin accounts
5. **User Roles**: Different user tiers (Free, Pro, Premium)
6. **Admin Permissions**: Granular admin permissions
7. **Rate Limiting**: API rate limiting
8. **Refresh Tokens**: Implement refresh token mechanism

## Troubleshooting

### Issue: "Invalid authentication credentials"
- Check if token is expired (30 minutes)
- Verify token is being sent in Authorization header
- Check SECRET_KEY matches between token creation and verification

### Issue: "User not found"
- Ensure user was registered in backend (check database)
- Verify email is correctly spelled

### Issue: "User account is not verified"
- Admin needs to approve the user first
- Check admin dashboard for pending users

### Issue: Admin cannot login
- Ensure admin account was created correctly
- Verify password hash is correct
- Check admin is active (active=True)

## File Structure

```
Backend:
├── app/
│   ├── api/
│   │   ├── auth.py          (NEW)
│   │   ├── admin.py         (NEW)
│   │   ├── analyze.py
│   │   └── reports.py
│   ├── core/
│   │   ├── auth.py          (NEW)
│   │   ├── security.py      (NEW)
│   │   └── ...
│   ├── db/
│   │   ├── schemas.py       (UPDATED)
│   │   ├── database.py
│   │   └── ...
│   └── main.py              (UPDATED)
└── requirements_updated.txt  (NEW)

Frontend:
├── src/
│   ├── components/
│   │   ├── AdminLogin.tsx       (NEW)
│   │   ├── AdminDashboard.tsx   (NEW)
│   │   ├── AdminRoute.tsx       (NEW)
│   │   ├── VerificationPending.tsx (NEW)
│   │   ├── Login.tsx            (UPDATED)
│   │   ├── Signup.tsx           (UPDATED)
│   │   └── ...
│   ├── App.tsx                  (UPDATED)
│   └── ...
```

## Support & Contact

For issues or questions, refer to the API documentation or check the console logs for detailed error messages.
