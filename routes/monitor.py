"""Monitoring endpoints for system health and diagnostics."""

from fastapi import APIRouter, Request

from utils.logger import get_logger

router = APIRouter(prefix="/api/monitor", tags=["monitoring"])
logger = get_logger(__name__)


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Explainable AI Code Vulnerability Auditor",
    }


@router.get("/stats")
async def get_system_stats(request: Request):
    """Get system statistics and diagnostics."""
    # This would be populated by storing references to clients in the app state
    stats = {
        "timestamp": "now",
        "api": {
            "model": "mixtral-8x7b-32768",
            "status": "operational",
        },
        "cache": {
            "enabled": True,
            "ttl_seconds": 3600,
        },
        "rate_limiting": {
            "enabled": True,
            "cooldown_seconds": 10,
        },
    }

    return stats
