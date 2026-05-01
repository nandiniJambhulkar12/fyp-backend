from app.db import schemas
from app.db.database import SessionLocal

s = SessionLocal()
users = s.query(schemas.User).all()
print('FOUND', len(users), 'users')
for u in users:
    print(u.id, u.email, 'verified=', u.verified, 'active=', u.active)
s.close()
