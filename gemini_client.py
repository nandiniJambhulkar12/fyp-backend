import json
import re
from typing import Any, Dict

import httpx

from config import Settings
from models import GeminiResponsePayload
from utils.logger import get_logger


logger = get_logger(__name__)


class DeepSeekClientError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class DeepSeekClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.endpoint = f"{settings.deepseek_api_base_url}/chat/completions"
        self.api_key = settings.deepseek_api_key

    async def analyze_code(self, prompt: str) -> GeminiResponsePayload:
        if not self.api_key:
            raise DeepSeekClientError("DEEPSEEK_API_KEY is not configured", status_code=500)

        payload = {
            "model": self.settings.deepseek_model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a cybersecurity vulnerability scanner. Always respond with valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_output_tokens,
            "response_format": {"type": "json_object"},
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.settings.deepseek_timeout_seconds) as client:
            response = await client.post(
                self.endpoint,
                headers=headers,
                json=payload,
            )

        if response.status_code >= 400:
            error_message = self._extract_error_message(response)
            logger.error(
                "deepseek.request_failed",
                extra={
                    "event": "deepseek.request_failed",
                    "status_code": response.status_code,
                    "response_body": response.text[:500],
                    "error_message": error_message,
                },
            )
            raise DeepSeekClientError(error_message, status_code=response.status_code)

        return self._parse_deepseek_response(response.json())

    def _parse_deepseek_response(self, payload: Dict[str, Any]) -> GeminiResponsePayload:
        try:
            text = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("DeepSeek returned an unexpected payload") from exc

        parsed_json = self._extract_json(text)
        try:
            return GeminiResponsePayload(**parsed_json)
        except Exception as exc:
            raise DeepSeekClientError("DeepSeek returned invalid JSON fields") from exc

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        stripped = text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return json.loads(stripped)

        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if not match:
            raise DeepSeekClientError("DeepSeek response did not contain JSON")
        return json.loads(match.group(0))

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            payload = {}

        message = ""
        if isinstance(payload, dict):
            error_payload = payload.get("error")
            if isinstance(error_payload, dict):
                message = str(error_payload.get("message") or "").strip()
            elif payload.get("message"):
                message = str(payload.get("message") or "").strip()

        if response.status_code == 429:
            return "RATE_LIMIT_EXCEEDED"
        if response.status_code == 402:
            return message or "DEEPSEEK_INSUFFICIENT_BALANCE"
        if response.status_code in {401, 403}:
            return message or "DEEPSEEK_AUTH_FAILED"
        if response.status_code == 404:
            return message or "DEEPSEEK_MODEL_NOT_FOUND"

        return message or "DEEPSEEK_UNAVAILABLE"


# Alias for backwards compatibility
GeminiClient = DeepSeekClient
GeminiClientError = DeepSeekClientError
