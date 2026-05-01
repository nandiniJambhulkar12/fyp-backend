import json
from typing import Optional, List

import httpx

from config import Settings
from models import GeminiResponsePayload
from utils.logger import get_logger
from utils.code_chunker import CodeChunker
from utils.retry_handler import RateLimitHandler, RetryConfig
from utils.result_cache import AnalysisResultCache


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
    """Groq API client with chunking, retry logic, and caching."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.api_key = settings.groq_api_key
        self.model = settings.groq_model
        self.timeout = settings.groq_timeout_seconds
        self.api_base_url = "https://api.groq.com/openai/v1"

        # Initialize utilities
        self.chunker = CodeChunker()
        self.retry_handler = RateLimitHandler(
            RetryConfig(
                max_retries=5,
                initial_delay=2.0,
                max_delay=30.0,
                exponential_base=2.0,
            )
        )
        self.cache = AnalysisResultCache(ttl_seconds=3600)

        if not self.api_key:
            raise GroqClientError("GROQ_API_KEY is not configured", status_code=500)

        logger.info(
            "groq.client_initialized",
            extra={
                "model": self.model,
                "timeout_seconds": self.timeout,
            },
        )

    async def analyze_code(self, prompt: str, code: str = "") -> GeminiResponsePayload:
        """
        Analyze code using Groq API with chunking and retry logic.

        Args:
            prompt: The analysis prompt
            code: Full source code for caching

        Returns:
            GeminiResponsePayload with vulnerability analysis
        """
        # Check cache first
        if code:
            cached_result = self.cache.get(code)
            if cached_result:
                logger.info(
                    "groq.cache_hit",
                    extra={"code_length": len(code)},
                )
                return cached_result

        # Check if code needs chunking
        if self.chunker.needs_chunking(code, threshold=self.settings.large_code_threshold):
            logger.info(
                "groq.chunking_enabled",
                extra={
                    "code_length": len(code),
                    "num_chunks": self.chunker.get_chunk_count(code),
                },
            )
            return await self._analyze_chunked(code)

        # Single analysis
        logger.debug(
            "groq.single_request",
            extra={"prompt_length": len(prompt)},
        )

        result = await self.retry_handler.call_with_retry(
            self._call_real_api,
            prompt,
        )

        # Cache result
        if code:
            self.cache.set(code, result)

        return result

    async def _analyze_chunked(self, code: str) -> GeminiResponsePayload:
        """
        Analyze large code by splitting into chunks.

        Args:
            code: Full source code

        Returns:
            Combined GeminiResponsePayload from all chunks
        """
        chunks = self.chunker.chunk_code(code, lines_per_chunk=self.settings.analysis_chunk_lines)
        all_findings = []
        max_severity = "Low"
        combined_explanation = []

        for idx, chunk in enumerate(chunks, 1):
            logger.info(
                "groq.chunk_processing",
                extra={
                    "chunk": f"{idx}/{len(chunks)}",
                    "chunk_lines": len(chunk.split('\n')),
                },
            )

            chunk_prompt = (
                f"Analyze this code chunk ({idx}/{len(chunks)}):\n\n"
                f"<code>\n{chunk}\n</code>"
            )

            try:
                result = await self.retry_handler.call_with_retry(
                    self._call_real_api,
                    chunk_prompt,
                )

                if result.vulnerability_detected:
                    chunk_findings = result.findings or [
                        {
                            "chunk": idx,
                            "issue": result.vulnerability_type,
                            "cwe_id": result.cwe_id,
                            "severity": result.risk_level,
                            "explanation": result.explanation,
                            "fix": result.recommended_fix,
                            "confidence": result.confidence_score,
                        }
                    ]
                    for finding in chunk_findings:
                        finding_copy = dict(finding)
                        finding_copy.setdefault("chunk", idx)
                        all_findings.append(finding_copy)
                    combined_explanation.append(
                        f"Chunk {idx}: {result.explanation}"
                    )

                    # Update max severity
                    severity_order = {"Critical": 3, "High": 2, "Medium": 1, "Low": 0}
                    if (severity_order.get(result.risk_level, 0) >
                        severity_order.get(max_severity, 0)):
                        max_severity = result.risk_level

            except GroqClientError as exc:
                logger.error(
                    "groq.chunk_failed",
                    extra={
                        "chunk": idx,
                        "error": str(exc),
                    },
                )
                raise

        # Combine results
        combined_result = GeminiResponsePayload(
            vulnerability_detected=len(all_findings) > 0,
            vulnerability_type="Multiple Issues" if len(all_findings) > 1 else (
                all_findings[0].get("issue", "") if all_findings else ""
            ),
            cwe_id=",".join(
                [f.get("cwe_id", f.get("cwe", "")) for f in all_findings if f.get("cwe_id") or f.get("cwe")]
            ),
            owasp_category="Multiple OWASP Categories",
            risk_level=max_severity,
            confidence_score=0.85 if all_findings else 0.0,
            explanation=" | ".join(combined_explanation) if combined_explanation else
            "No vulnerabilities detected in any chunk.",
            recommended_fix="Review issues in each chunk individually.",
            findings=all_findings,
        )

        logger.info(
            "groq.chunked_analysis_complete",
            extra={
                "num_chunks": len(chunks),
                "findings": len(all_findings),
                "max_severity": max_severity,
            },
        )

        return combined_result

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
            "temperature": self.settings.groq_temperature,
            "top_p": 1.0,
            "max_tokens": self.settings.groq_max_tokens,
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
                    logger.warning("groq.rate_limit_429")
                    raise GroqClientError(
                        "Groq API rate limit exceeded (429).",
                        status_code=429,
                    )
                elif response.status_code >= 500:
                    logger.error("groq.server_error", extra={"status": response.status_code})
                    raise GroqClientError(
                        f"Groq API server error (HTTP {response.status_code}).",
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
                "Groq API request timed out.",
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
        Parse Groq API response.

        Args:
            response_text: Raw response from Groq API

        Returns:
            GeminiResponsePayload with extracted vulnerability data
        """
        try:
            response_json = json.loads(response_text)

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
                    findings=findings,
                )
            else:
                payload = GeminiResponsePayload(
                    vulnerability_detected=False,
                    vulnerability_type="",
                    cwe_id="",
                    owasp_category="",
                    risk_level="Low",
                    confidence_score=0.0,
                    explanation="No security vulnerabilities detected.",
                    recommended_fix="",
                    findings=[],
                )

            logger.info(
                "groq.analysis_complete",
                extra={
                    "vulnerability_detected": payload.vulnerability_detected,
                    "risk_level": payload.risk_level,
                },
            )

            return payload

        except (json.JSONDecodeError, KeyError, IndexError, ValueError) as exc:
            logger.error("groq.parse_error", extra={"error": str(exc)})
            raise GroqClientError(
                f"Failed to parse Groq API response: {str(exc)}",
                status_code=502,
            )

    def _extract_json(self, text: str) -> Optional[dict]:
        """Extract JSON from response text."""
        import re

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return None
