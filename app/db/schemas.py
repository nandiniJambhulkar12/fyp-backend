from sqlalchemy import Column, String, JSON, Boolean, DateTime, Integer, ForeignKey
from app.db.database import Base, engine
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime


class User(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    firebase_uid = Column(String, nullable=True, index=True)
    name = Column(String)
    phone = Column(String, nullable=True)
    verified = Column(Boolean, default=False)
    active = Column(Boolean, default=True)
    role = Column(String, default='user')  # 'user', 'admin'
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Admin(Base):
    __tablename__ = 'admins'
    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    hashed_password = Column(String)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Report(Base):
    __tablename__ = 'reports'
    id = Column(String, primary_key=True, index=True)
    findings = Column(JSON)
    summary = Column(JSON)


class AnalysisHistory(Base):
    __tablename__ = 'analysis_history'
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey('users.id'), index=True)
    code_snippet = Column(String)
    language = Column(String)
    findings = Column(JSON)  # Stored findings from analysis
    risk_level = Column(String)  # High, Medium, Low
    vulnerability_count = Column(Integer, default=0)
    analysis_date = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


# Pydantic schemas (API request/response models)
class UserCreate(BaseModel):
    email: str
    name: str
    firebase_uid: str = None


class UserUpdate(BaseModel):
    verified: bool = None
    active: bool = None
    phone: str = None
    name: str = None


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    phone: str = None
    verified: bool
    active: bool
    role: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


class AdminLogin(BaseModel):
    email: str
    password: str


class AdminResponse(BaseModel):
    id: str
    email: str
    name: str
    created_at: datetime
    
    class Config:
        orm_mode = True


class ReportCreate(BaseModel):
    id: str
    findings: list
    summary: dict


class AnalysisHistoryCreate(BaseModel):
    code_snippet: str
    language: str
    findings: list
    risk_level: str
    vulnerability_count: int = 0


class AnalysisHistoryResponse(BaseModel):
    id: str
    user_id: str
    code_snippet: str
    language: str
    findings: list
    risk_level: str
    vulnerability_count: int
    analysis_date: datetime
    created_at: datetime
    
    class Config:
        orm_mode = True

# DB helpers


def create_user(db: Session, user_create: UserCreate, user_id: str) -> User:
    db_user = User(
        id=user_id,
        email=user_create.email,
        name=user_create.name,
        verified=False,
        active=True,
        role='user'
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_user_by_email(db: Session, email: str) -> User:
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: str) -> User:
    return db.query(User).filter(User.id == user_id).first()


def get_all_users(db: Session):
    return db.query(User).all()


def update_user(db: Session, user_id: str, user_update: UserUpdate) -> User:
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        return None
    if user_update.verified is not None:
        db_user.verified = user_update.verified
    if user_update.active is not None:
        db_user.active = user_update.active
    if user_update.phone is not None:
        db_user.phone = user_update.phone
    if user_update.name is not None:
        db_user.name = user_update.name
    db_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, user_id: str) -> bool:
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        return False
    db.delete(db_user)
    db.commit()
    return True


def get_admin_by_email(db: Session, email: str) -> Admin:
    return db.query(Admin).filter(Admin.email == email).first()


def get_admin_by_id(db: Session, admin_id: str) -> Admin:
    return db.query(Admin).filter(Admin.id == admin_id).first()


def create_admin(db: Session, email: str, name: str, hashed_password: str, admin_id: str) -> Admin:
    db_admin = Admin(
        id=admin_id,
        email=email,
        name=name,
        hashed_password=hashed_password,
        active=True
    )
    db.add(db_admin)
    db.commit()
    db.refresh(db_admin)
    return db_admin


def save_report(db: Session, report: ReportCreate):
    r = Report(id=report.id, findings=report.findings, summary=report.summary)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def get_report(db: Session, report_id: str):
    return db.query(Report).filter(Report.id == report_id).first()


def save_analysis_history(
    db: Session,
    user_id: str,
    analysis_create: AnalysisHistoryCreate,
    history_id: str
) -> AnalysisHistory:
    """Save code analysis to user's history."""
    history = AnalysisHistory(
        id=history_id,
        user_id=user_id,
        code_snippet=analysis_create.code_snippet,
        language=analysis_create.language,
        findings=analysis_create.findings,
        risk_level=analysis_create.risk_level,
        vulnerability_count=analysis_create.vulnerability_count
    )
    db.add(history)
    db.commit()
    db.refresh(history)
    return history


def get_analysis_history(
    db: Session,
    user_id: str,
    limit: int = 50,
    offset: int = 0
) -> list:
    """Get analysis history for a user, ordered by date descending."""
    return db.query(AnalysisHistory).filter(
        AnalysisHistory.user_id == user_id
    ).order_by(AnalysisHistory.analysis_date.desc()).offset(offset).limit(limit).all()


def get_analysis_by_id(
    db: Session,
    user_id: str,
    analysis_id: str
) -> AnalysisHistory:
    """Get specific analysis by ID (verify user ownership)."""
    return db.query(AnalysisHistory).filter(
        AnalysisHistory.id == analysis_id,
        AnalysisHistory.user_id == user_id
    ).first()


def delete_analysis(
    db: Session,
    user_id: str,
    analysis_id: str
) -> bool:
    """Delete analysis by ID (verify user ownership)."""
    analysis = get_analysis_by_id(db, user_id, analysis_id)
    if not analysis:
        return False
    db.delete(analysis)
    db.commit()
    return True
