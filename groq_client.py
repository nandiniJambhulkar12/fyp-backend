import json
from typing import Optional

import httpx

from config import Settings
from models import GeminiResponsePayload
from utils.logger import get_logger


logger = get_logger(__name__)


class GroqClientError(Exception):
    """Custom exception for Groq client errors."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

    def __str__(self):
        return self.message


class GroqClient:
    """Groq API client for code vulnerability analysis."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.api_key = settings.groq_api_key
        self.model = settings.groq_model
        self.timeout = settings.groq_timeout_seconds
        self.api_base_url = "https://api.groq.com/openai/v1"

        if not self.api_key:
            raise GroqClientError("GROQ_API_KEY is not configured", status_code=500)

        logger.info(
            "groq.client_initialized",
            extra={
                "model": self.model,
                "timeout_seconds": self.timeout,
            },
        )

    async def analyze_code(self, prompt: str) -> GeminiResponsePayload:
        """
        Analyze code using ONLY Groq API - no fallback to mock/dummy responses.

        Args:
            prompt: The analysis prompt containing code to analyze

        Returns:
            GeminiResponsePayload with vulnerability analysis from real API

        Raises:
            GroqClientError: If API call fails
        """
        logger.debug(
            "groq.request_sent",
            extra={
                "model": self.model,
                "prompt_length": len(prompt),
            },
        )

        # ONLY real API calls - NO fallback, NO mock, NO dummy responses
        return await self._call_real_api(prompt)

    async def _call_real_api(self, prompt: str) -> GeminiResponsePayload:
        """
        Make actual HTTP request to Groq API.

        Args:
            prompt: The analysis prompt

        Returns:
            GeminiResponsePayload with vulnerability analysis

        Raises:
            GroqClientError: If API call fails
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a senior security auditor and code vulnerability scanner.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 2000,
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
                    logger.error("groq.auth_failed", extra={"status": 401})
                    raise GroqClientError(
                        "Groq API authentication failed. Invalid API key.",
                        status_code=401,
                    )
                elif response.status_code == 429:
                    logger.warning("groq.rate_limit")
                    raise GroqClientError(
                        "Groq API rate limit exceeded. Please wait before retrying.",
                        status_code=429,
                    )
                elif response.status_code >= 500:
                    logger.error("groq.server_error", extra={"status": response.status_code})
                    raise GroqClientError(
                        f"Groq API server error (HTTP {response.status_code}). Please try again later.",
                        status_code=503,
                    )
                elif response.status_code >= 400:
                    logger.error("groq.client_error", extra={"status": response.status_code})
                    raise GroqClientError(
                        f"Groq API error (HTTP {response.status_code}): {response.text}",
                        status_code=response.status_code,
                    )

                return self._parse_groq_response(response.text)

        except httpx.TimeoutException:
            logger.error("groq.timeout")
            raise GroqClientError(
                "Groq API request timed out. Please try again.",
                status_code=504,
            )
        except httpx.RequestError as exc:
            logger.error("groq.request_error", extra={"error": str(exc)})
            raise GroqClientError(
                f"Groq API request failed: {str(exc)}",
                status_code=502,
            )

    def _parse_groq_response(self, response_text: str) -> GeminiResponsePayload:
        """
        Parse Groq API response with findings array format.

        Args:
            response_text: Raw response from Groq API

        Returns:
            GeminiResponsePayload with extracted vulnerability data
        """
        try:
            response_json = json.loads(response_text)

            # Get message content from response
            if "choices" not in response_json or not response_json["choices"]:
                raise GroqClientError("Invalid response format from Groq API", 502)

            message_content = response_json["choices"][0].get("message", {}).get("content", "")

            # Extract JSON from response
            analysis_json = self._extract_json(message_content)

            if not analysis_json:
                logger.warning(
                    "groq.json_extraction_failed",
                    extra={"content_preview": message_content[:200]},
                )
                raise GroqClientError(
                    "Failed to extract vulnerability analysis from API response",
                    status_code=502,
                )

            # Handle findings array format
            vulnerabilities_found = analysis_json.get("vulnerabilities_found", False)
            findings = analysis_json.get("findings", [])

            # If findings exist, use the most critical one
            if findings and vulnerabilities_found:
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
                "groq.analysis_complete",
                extra={
                    "vulnerability_detected": payload.vulnerability_detected,
                    "risk_level": payload.risk_level,
                    "findings_count": len(findings),
                },
            )

            return payload

        except (json.JSONDecodeError, KeyError, IndexError, ValueError) as exc:
            logger.error(
                "groq.parse_error",
                extra={"error": str(exc)},
            )
            raise GroqClientError(
                f"Failed to parse Groq API response: {str(exc)}",
                status_code=502,
            )

    def _extract_json(self, text: str) -> Optional[dict]:
        """
        Extract JSON object from text, handling markdown code blocks.

        Args:
            text: Text that may contain JSON

        Returns:
            Parsed JSON dict or None if extraction fails
        """
        # Try direct JSON parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        import re
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Try finding JSON object in text
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return None
