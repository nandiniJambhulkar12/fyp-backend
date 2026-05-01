import json
import re
from typing import Any, Dict

import httpx

from config import Settings
from models import GeminiResponsePayload
from utils.logger import get_logger


logger = get_logger(__name__)


class HFClientError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class HFClient:
    """HuggingFace API client for code vulnerability analysis."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.endpoint = f"{settings.hf_api_base_url}/{settings.hf_model}"
        self.api_key = settings.hf_api_key

    async def analyze_code(self, prompt: str) -> GeminiResponsePayload:
        if not self.api_key:
            raise HFClientError("HF_API_KEY is not configured", status_code=500)

        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": self.settings.max_output_tokens,
                "temperature": self.settings.temperature,
            },
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.settings.hf_timeout_seconds) as client:
            response = await client.post(
                self.endpoint,
                headers=headers,
                json=payload,
            )

        if response.status_code >= 400:
            error_message = self._extract_error_message(response)
            logger.error(
                "hf.request_failed",
                extra={
                    "event": "hf.request_failed",
                    "status_code": response.status_code,
                    "response_body": response.text[:500],
                    "error_message": error_message,
                },
            )
            raise HFClientError(error_message, status_code=response.status_code)

        return self._parse_hf_response(response.json())

    def _parse_hf_response(self, payload: Any) -> GeminiResponsePayload:
        """Parse HuggingFace API response and extract JSON."""
        try:
            # HF returns a list of results
            if isinstance(payload, list) and len(payload) > 0:
                result = payload[0]
                if isinstance(result, dict) and "generated_text" in result:
                    text = result["generated_text"]
                else:
                    text = str(result)
            else:
                text = str(payload)
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("HuggingFace returned an unexpected payload") from exc

        parsed_json = self._extract_json(text)
        try:
            return GeminiResponsePayload(**parsed_json)
        except Exception as exc:
            raise HFClientError("HuggingFace returned invalid JSON fields") from exc

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        """Extract JSON from text, handling markdown code blocks."""
        stripped = text.strip()
        
        # Try to find JSON code block
        code_block = re.search(r"```(?:json)?\s*([\s\S]*?)```", stripped)
        if code_block:
            stripped = code_block.group(1).strip()
        
        # Try direct JSON parsing
        if stripped.startswith("{") and stripped.endswith("}"):
            return json.loads(stripped)

        # Try to find JSON object in text
        match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", stripped, re.DOTALL)
        if match:
            return json.loads(match.group(0))

        raise HFClientError("HuggingFace response did not contain valid JSON")

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        """Extract error message from HuggingFace API response."""
        try:
            payload = response.json()
        except ValueError:
            payload = {}

        message = ""
        if isinstance(payload, dict):
            if "error" in payload:
                error = payload["error"]
                if isinstance(error, str):
                    message = error
                elif isinstance(error, dict):
                    message = str(error.get("message") or "").strip()
            elif "message" in payload:
                message = str(payload.get("message") or "").strip()

        if response.status_code == 429:
            return "RATE_LIMIT_EXCEEDED"
        if response.status_code == 401:
            return message or "HF_INVALID_API_KEY"
        if response.status_code == 503:
            return message or "HF_MODEL_LOADING"
        if response.status_code == 402:
            return message or "HF_INSUFFICIENT_BALANCE"

        return message or "HF_UNAVAILABLE"
