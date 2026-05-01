from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.api import analyze, reports, admin, auth, history
from app.db.database import Base, engine, get_db
from app.core.security import get_current_user
from sqlalchemy.orm import Session
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create all tables on startup
try:
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")
except Exception as e:
    logger.error(f"Error creating database tables: {str(e)}", exc_info=True)

app = FastAPI(title="XAI Code Auditor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(auth.router)
app.include_router(history.router)
app.include_router(admin.router)


@app.get("/")
async def root():
    return {"status": "running", "service": "xai-code-auditor"}


@app.get("/api/debug/status")
async def debug_status(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Debug endpoint to check system status."""
    from app.db import schemas
    
    try:
        user = schemas.get_user_by_id(db, current_user["user_id"])
        history_count = len(schemas.get_analysis_history(db, current_user["user_id"], limit=1000))
        
        return {
            "status": "ok",
            "authenticated_user": {
                "user_id": current_user["user_id"],
                "email": user.email if user else "unknown"
            },
            "analysis_count": history_count,
            "database": "connected"
        }
    except Exception as e:
        logger.error(f"Debug status check error: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }
