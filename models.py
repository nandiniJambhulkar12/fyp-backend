from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class ParsedCode(BaseModel):
    file_name: str
    language: str
    code_content: str
    truncated_code: str
    code_hash: str


class VulnerabilityReport(BaseModel):
    file_name: str
    language: str
    vulnerability_detected: bool
    vulnerability_type: str
    cwe_id: str
    owasp_category: str
    risk_level: str
    confidence_score: float
    explanation: str
    recommended_fix: str

    @validator("language", "vulnerability_type", "cwe_id", "owasp_category", "risk_level", "explanation", "recommended_fix", pre=True)
    def normalize_strings(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()


class AnalyzeResponse(VulnerabilityReport):
    findings: Optional[List[Dict[str, Any]]] = Field(default=None)
    history_id: Optional[str] = None
    dataset_risk: Optional[Dict[str, Any]] = None


class AuthLoginRequest(BaseModel):
    email: str
    firebase_uid: Optional[str] = None


class AuthRegisterRequest(BaseModel):
    email: str
    name: str


class VerifyStatusRequest(BaseModel):
    email: str


class ProfileUpdateRequest(BaseModel):
    name: str
    phone: Optional[str] = None


class UserProfile(BaseModel):
    id: str
    name: str
    email: str
    phone: Optional[str] = None
    verified: bool = True
    active: bool = True
    role: str = "user"
    created_at: str
    updated_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class HistoryEntry(BaseModel):
    id: str
    user_email: str
    file_name: str
    language: str
    risk_level: str
    vulnerability_count: int
    vulnerability_detected: bool
    analysis_date: str
    findings: List[Dict[str, Any]] = Field(default_factory=list)


class GeminiResponsePayload(BaseModel):
    vulnerability_detected: bool = False
    vulnerability_type: str = ""
    cwe_id: str = ""
    owasp_category: str = ""
    risk_level: str = "Low"
    confidence_score: float = 0.0
    explanation: str = ""
    recommended_fix: str = ""
    findings: Optional[List[Dict[str, Any]]] = Field(default=None)