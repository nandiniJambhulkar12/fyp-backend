from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

import firebase_admin
from firebase_admin import credentials

from config import get_settings
from routes.auth import router as auth_router
from routes.analyze import router as analyze_router
from routes.history import router as history_router
from utils.analysis_queue import get_analysis_queue
from utils.logger import configure_logging, get_logger


settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.firebase_service_account_path:
        try:
            cred = credentials.Certificate(settings.firebase_service_account_path)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
    queue = get_analysis_queue(settings.analysis_queue_workers, settings.scan_cooldown_seconds)
    await queue.start()
    logger.info(
        "backend.startup",
        extra={
            "event": "backend.startup",
            "groq_model": settings.groq_model,
            "max_code_characters": settings.max_code_characters,
            "large_code_threshold": settings.large_code_threshold,
            "analysis_chunk_lines": settings.analysis_chunk_lines,
            "analysis_queue_workers": settings.analysis_queue_workers,
            "rate_limit_rpm": settings.rate_limit_requests_per_minute,
            "cooldown_seconds": settings.scan_cooldown_seconds,
        },
    )
    yield
    await queue.stop()
    logger.info("backend.shutdown", extra={"event": "backend.shutdown"})


app = FastAPI(
    title="Explainable AI Code Vulnerability Auditor",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started_at = perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        logger.info(
            "http.request",
            extra={
                "event": "http.request",
                "method": request.method,
                "path": request.url.path,
                "status_code": getattr(response, "status_code", 500),
                "duration_ms": duration_ms,
                "client_ip": request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown"),
            },
        )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": "Invalid request payload", "errors": exc.errors()})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    logger.exception("http.unhandled_error", extra={"event": "http.unhandled_error"})
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/")
async def healthcheck():
    return {"status": "running", "service": "groq-vulnerability-auditor"}


app.include_router(analyze_router, prefix="/api", tags=["analysis"])
app.include_router(auth_router, prefix="/api", tags=["auth"])
app.include_router(history_router, prefix="/api", tags=["history"])