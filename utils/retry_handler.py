"""Retry logic with exponential backoff for API calls."""

import asyncio
import random
from typing import Callable, Optional, TypeVar, Any
from utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int = 5,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt with exponential backoff."""
        delay = self.initial_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)

        if self.jitter:
            # Add random jitter (±10%)
            jitter_amount = delay * 0.1
            delay += random.uniform(-jitter_amount, jitter_amount)

        return max(0.1, delay)  # Minimum 0.1s


class RateLimitHandler:
    """Handle API rate limits with retry logic."""

    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()

    async def call_with_retry(
        self,
        func: Callable[..., Any],
        *args,
        **kwargs
    ) -> Any:
        """
        Call function with automatic retry on rate limit (429).

        Args:
            func: Async function to call
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Function result

        Raises:
            Exception: Final exception if all retries exhausted
        """
        last_exception = None

        for attempt in range(self.config.max_retries + 1):
            try:
                logger.debug(
                    "retry.attempt",
                    extra={
                        "attempt": attempt + 1,
                        "max_retries": self.config.max_retries + 1,
                    },
                )
                return await func(*args, **kwargs)

            except Exception as exc:
                last_exception = exc
                error_str = str(exc)

                # Check if it's a rate limit error
                is_rate_limit = (
                    "429" in error_str or
                    "rate limit" in error_str.lower() or
                    "too many requests" in error_str.lower()
                )

                if is_rate_limit and attempt < self.config.max_retries:
                    delay = self.config.get_delay(attempt)
                    logger.warning(
                        "rate_limit.detected",
                        extra={
                            "attempt": attempt + 1,
                            "retry_delay": delay,
                            "error": error_str[:100],
                        },
                    )
                    await asyncio.sleep(delay)
                    continue

                # Not a rate limit error or no retries left
                raise

        # Should not reach here, but raise last exception just in case
        raise last_exception
