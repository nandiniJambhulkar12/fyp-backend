from functools import lru_cache
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from config import get_settings
from groq_client_v2 import GroqClient, GroqClientError
from models import AnalyzeResponse
from routes.auth import get_store, get_token_manager
from utils.analysis_queue import get_analysis_queue
from utils.cache import AnalysisCache
from utils.file_parser import parse_code_input
from utils.logger import get_logger
from vulnerability_analyzer import VulnerabilityAnalyzer


router = APIRouter()
logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_cache() -> AnalysisCache:
    settings = get_settings()
    return AnalysisCache(settings.cache_path, settings.cache_ttl_seconds)


@lru_cache(maxsize=1)
def get_analyzer() -> VulnerabilityAnalyzer:
    settings = get_settings()
    return VulnerabilityAnalyzer(
        settings=settings,
        cache=get_cache(),
        groq_client=GroqClient(settings),
    )


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _user_email_from_request(request: Request) -> Optional[str]:
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = get_token_manager().verify_token(token)
    except ValueError:
        return None
    email = payload.get("email")
    return email if isinstance(email, str) and email else None


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_code(
    request: Request,
    file: Optional[UploadFile] = File(default=None),
    code: Optional[str] = Form(default=None),
    language: Optional[str] = Form(default=None),
):
    if file is None and not code:
        raise HTTPException(status_code=400, detail="Either a code file or code text is required")

    settings = get_settings()
    parsed_code = await parse_code_input(
        file=file,
        code=code,
        declared_language=language,
        settings=settings,
    )
    logger.info(
        "analysis.received",
        extra={
            "event": "analysis.received",
            "client_ip": _client_ip(request),
            "file_name": parsed_code.file_name,
            "language": parsed_code.language,
            "code_hash": parsed_code.code_hash,
            "code_length": len(parsed_code.truncated_code),
        },
    )
    try:
        queue = get_analysis_queue(settings.analysis_queue_workers, settings.scan_cooldown_seconds)
        response = await queue.submit(get_analyzer().analyze, parsed_code)
    except GroqClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    user_email = _user_email_from_request(request)
    if user_email and get_store().get_user(user_email):
        history_entry = get_store().add_history(
            user_email=user_email,
            file_name=parsed_code.file_name,
            language=parsed_code.language,
            risk_level=response.risk_level,
            vulnerability_detected=response.vulnerability_detected,
            findings=response.findings or [],
        )
        response.history_id = history_entry.id

    return response
