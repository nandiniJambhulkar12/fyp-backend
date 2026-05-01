import json
import re
from typing import Optional

import httpx

from config import Settings
from models import GeminiResponsePayload
from utils.logger import get_logger


logger = get_logger(__name__)


class BytezClientError(Exception):
    """Custom exception for Bytez client errors."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

    def __str__(self):
        return self.message


class BytezClient:
    """Bytez API client for code vulnerability analysis with mock fallback."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.api_key = settings.bytez_api_key
        self.model = settings.bytez_model
        self.timeout = settings.bytez_timeout_minutes * 60  # Convert to seconds
        # Corrected endpoint (api.bytez.io not api.bytez.ai)
        self.api_base_url = "https://api.bytez.io/v1"

        if not self.api_key:
            raise BytezClientError("BYTEZ_API_KEY is not configured", status_code=500)

        logger.info(
            "bytez.client_initialized",
            extra={
                "model": self.model,
                "timeout_seconds": self.timeout,
            },
        )

    async def analyze_code(self, prompt: str) -> GeminiResponsePayload:
        """
        Analyze code using ONLY Bytez API - no fallback to mock/dummy responses.

        Args:
            prompt: The analysis prompt containing code to analyze

        Returns:
            GeminiResponsePayload with vulnerability analysis from real API

        Raises:
            BytezClientError: If API call fails - always raises, never falls back
        """
        logger.debug(
            "bytez.request_sent",
            extra={
                "model": self.model,
                "prompt_length": len(prompt),
            },
        )

        # ONLY real API calls - NO fallback, NO mock, NO dummy responses
        return await self._call_real_api(prompt)

    async def _call_real_api(self, prompt: str) -> GeminiResponsePayload:
        """Call the actual Bytez API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a cybersecurity vulnerability scanner. Analyze code and return ONLY valid JSON with vulnerability details.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_output_tokens,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.api_base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )

                # Handle HTTP errors
                if response.status_code == 401:
                    logger.error("bytez.auth_failed", extra={"status": 401})
                    raise BytezClientError(
                        "Bytez API authentication failed. Invalid API key.",
                        status_code=401,
                    )
                elif response.status_code == 429:
                    logger.warning("bytez.rate_limit")
                    raise BytezClientError(
                        "Bytez API rate limit exceeded. Please wait before retrying.",
                        status_code=429,
                    )
                elif response.status_code == 404:
                    logger.error(
                        "bytez.model_not_found",
                        extra={"model": self.model},
                    )
                    raise BytezClientError(
                        f"Bytez model '{self.model}' not found.",
                        status_code=404,
                    )
                elif response.status_code >= 500:
                    logger.error(
                        "bytez.server_error",
                        extra={"status": response.status_code},
                    )
                    raise BytezClientError(
                        "Bytez API server error. Please try again later.",
                        status_code=503,
                    )
                elif response.status_code >= 400:
                    error_msg = self._extract_error_message(response.text)
                    logger.error(
                        "bytez.request_failed",
                        extra={"status": response.status_code, "error": error_msg},
                    )
                    raise BytezClientError(error_msg, status_code=response.status_code)

                # Parse successful response
                logger.info("bytez.request_success")
                return self._parse_bytez_response(response.text)

        except httpx.TimeoutException:
            logger.error(
                "bytez.timeout",
                extra={"timeout_seconds": self.timeout},
            )
            raise BytezClientError(
                f"Bytez API request timeout after {self.timeout}s",
                status_code=504,
            )
        except httpx.RequestError as exc:
            logger.error(
                "bytez.connection_error",
                extra={"error": str(exc)},
            )
            raise BytezClientError(
                f"Bytez API connection error: {str(exc)}", status_code=503
            )

    def _get_mock_response(self, prompt: str) -> GeminiResponsePayload:
        """Return a mock vulnerability response for testing."""
        code = self._extract_code_from_prompt(prompt)
        mock_data = self._detect_mock_vulnerability(code)
        
        logger.info(
            "bytez.mock_response",
            extra={
                "vulnerability_detected": mock_data["vulnerability_detected"],
                "risk_level": mock_data["risk_level"],
            },
        )

        return GeminiResponsePayload(
            vulnerability_detected=mock_data["vulnerability_detected"],
            vulnerability_type=mock_data["vulnerability_type"],
            cwe_id=mock_data["cwe_id"],
            owasp_category=mock_data["owasp_category"],
            risk_level=mock_data["risk_level"],
            confidence_score=mock_data["confidence_score"],
            explanation=mock_data["explanation"],
            recommended_fix=mock_data["recommended_fix"],
        )

    def _parse_bytez_response(self, response_text: str) -> GeminiResponsePayload:
        """
        Parse Bytez API response with new findings array format.

        Args:
            response_text: Raw response from Bytez API

        Returns:
            GeminiResponsePayload with extracted vulnerability data
        """
        try:
            response_json = json.loads(response_text)

            # Get message content from response
            if "choices" not in response_json or not response_json["choices"]:
                raise BytezClientError("Invalid response format from Bytez API", 502)

            message_content = response_json["choices"][0].get("message", {}).get("content", "")

            # Extract JSON from response
            analysis_json = self._extract_json(message_content)

            if not analysis_json:
                logger.warning(
                    "bytez.json_extraction_failed",
                    extra={"content_preview": message_content[:200]},
                )
                raise BytezClientError(
                    "Failed to extract vulnerability analysis from API response",
                    status_code=502,
                )

            # Handle new findings array format
            vulnerabilities_found = analysis_json.get("vulnerabilities_found", False)
            findings = analysis_json.get("findings", [])

            # If findings exist, use the most critical one for the single payload
            if findings and vulnerabilities_found:
                # Sort by severity to get the most critical
                severity_order = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
                most_critical = max(
                    findings,
                    key=lambda x: severity_order.get(x.get("severity", "Low"), 0)
                )

                payload = GeminiResponsePayload(
                    vulnerability_detected=True,
                    vulnerability_type=most_critical.get("issue", ""),
                    cwe_id=most_critical.get("cwe_id", ""),
                    owasp_category=most_critical.get("owasp", ""),
                    risk_level=most_critical.get("severity", "Unknown"),
                    confidence_score=float(most_critical.get("confidence", 0.0)),
                    explanation=most_critical.get("explanation", ""),
                    recommended_fix=most_critical.get("fix", ""),
                )
            else:
                # No vulnerabilities found
                payload = GeminiResponsePayload(
                    vulnerability_detected=False,
                    vulnerability_type="",
                    cwe_id="",
                    owasp_category="",
                    risk_level="Low",
                    confidence_score=0.0,
                    explanation="No security vulnerabilities detected in the analyzed code.",
                    recommended_fix="",
                )

            logger.info(
                "bytez.analysis_complete",
                extra={
                    "vulnerability_detected": payload.vulnerability_detected,
                    "risk_level": payload.risk_level,
                    "findings_count": len(findings),
                },
            )

            return payload

        except (json.JSONDecodeError, KeyError, IndexError, ValueError) as exc:
            logger.error(
                "bytez.parse_error",
                extra={"error": str(exc)},
            )
            raise BytezClientError(
                f"Failed to parse Bytez API response: {str(exc)}",
                status_code=502,
            )

    def _extract_json(self, text: str) -> Optional[dict]:
        """
        Extract JSON from text, handling markdown code blocks.

        Args:
            text: Text potentially containing JSON

        Returns:
            Parsed JSON dict or None if extraction fails
        """
        # Try to find JSON in markdown code blocks
        json_match = re.search(r"```(?:json)?\s*({.*?})\s*```", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try direct JSON parsing
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find any valid JSON object in text
        try:
            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(text[json_start:json_end])
        except json.JSONDecodeError:
            pass

        return None

    def _extract_error_message(self, response_text: str) -> str:
        """
        Extract meaningful error message from API response.

        Args:
            response_text: Raw error response

        Returns:
            Formatted error message
        """
        try:
            error_json = json.loads(response_text)
            if "error" in error_json:
                if isinstance(error_json["error"], dict):
                    return error_json["error"].get("message", str(error_json["error"]))
                return str(error_json["error"])
            if "message" in error_json:
                return error_json["message"]
        except json.JSONDecodeError:
            pass

        # Return first 200 chars of response as fallback
        return response_text[:200] if response_text else "Unknown error"
