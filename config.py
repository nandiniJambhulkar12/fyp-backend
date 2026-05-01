from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    secret_key: str = Field("local-dev-secret-key", env="SECRET_KEY")
    gemini_api_key: str = Field("", env="GEMINI_API_KEY")
    gemini_model: str = Field("gemini-2.0-flash", env="GEMINI_MODEL")
    gemini_api_base_url: str = Field(
        "https://generativelanguage.googleapis.com/v1beta",
        env="GEMINI_API_BASE_URL",
    )
    gemini_timeout_seconds: float = Field(30.0, env="GEMINI_TIMEOUT_SECONDS")
    temperature: float = Field(0.2, env="GEMINI_TEMPERATURE")
    max_output_tokens: int = Field(200, env="GEMINI_MAX_OUTPUT_TOKENS")
    bytez_api_key: str = Field("", env="BYTEZ_API_KEY")
    bytez_model: str = Field("deepseek-ai/deepseek-coder", env="BYTEZ_MODEL")
    bytez_timeout_minutes: int = Field(10, env="BYTEZ_TIMEOUT_MINUTES")
    deepseek_api_key: str = Field("", env="DEEPSEEK_API_KEY")
    deepseek_model: str = Field("deepseek-v4-flash", env="DEEPSEEK_MODEL")
    deepseek_api_base_url: str = Field(
        "https://api.deepseek.com/v1",
        env="DEEPSEEK_API_BASE_URL",
    )
    deepseek_timeout_seconds: float = Field(30.0, env="DEEPSEEK_TIMEOUT_SECONDS")
    groq_api_key: str = Field("", env="GROQ_API_KEY")
    groq_model: str = Field("llama-3.1-8b-instant", env="GROQ_MODEL")
    groq_temperature: float = Field(0.0, env="GROQ_TEMPERATURE")
    groq_max_tokens: int = Field(4096, env="GROQ_MAX_TOKENS")
    groq_timeout_seconds: float = Field(30.0, env="GROQ_TIMEOUT_SECONDS")
    max_file_size_bytes: int = Field(1_048_576, env="MAX_FILE_SIZE_BYTES")
    max_code_characters: int = Field(500_000, env="MAX_CODE_CHARACTERS")
    large_code_threshold: int = Field(5000, env="LARGE_CODE_THRESHOLD")
    analysis_chunk_lines: int = Field(800, env="ANALYSIS_CHUNK_LINES")
    analysis_queue_workers: int = Field(1, env="ANALYSIS_QUEUE_WORKERS")
    rate_limit_requests_per_minute: int = Field(1000, env="RATE_LIMIT_REQUESTS_PER_MINUTE")
    scan_cooldown_seconds: int = Field(10, env="SCAN_COOLDOWN_SECONDS")
    cache_ttl_seconds: int = Field(604800, env="CACHE_TTL_SECONDS")
    cache_file_path: str = Field(".cache/analysis_cache.json", env="CACHE_FILE_PATH")
    users_file_path: str = Field(".cache/users.json", env="USERS_FILE_PATH")
    history_file_path: str = Field(".cache/history.json", env="HISTORY_FILE_PATH")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    cors_origins_raw: str = Field(
        "http://localhost:3000,http://127.0.0.1:3000",
        env="CORS_ORIGINS",
    )
    enable_legacy_response_fields: bool = Field(True, env="ENABLE_LEGACY_RESPONSE_FIELDS")

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def cors_origins(self) -> List[str]:
        origins = [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]
        return origins or ["*"]

    @property
    def cache_path(self) -> Path:
        return Path(self.cache_file_path)

    @property
    def users_path(self) -> Path:
        return Path(self.users_file_path)

    @property
    def history_path(self) -> Path:
        return Path(self.history_file_path)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()