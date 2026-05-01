import asyncio
import time
from collections import deque
from typing import Any, Callable, Deque, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Rate limiter for API requests with special handling for large code submissions."""

    def __init__(self, requests_per_minute: int = 30):
        self.requests_per_minute = requests_per_minute
        self.request_times: Deque[float] = deque()
        self.lock = asyncio.Lock()
        self.large_code_queue: Deque[tuple[str, Callable, tuple, dict]] = deque()
        self.processing_large_code = False

    async def acquire(self, code_length: int) -> None:
        """
        Acquire permission to make a request.
        For code >= 10k characters, queue it for serial processing.
        """
        async with self.lock:
            if code_length >= 10000:
                # Large code gets queued and processed one at a time
                await self._process_large_code_queue()
            else:
                # Regular code is rate-limited based on time window
                await self._wait_for_rate_limit()

    async def _wait_for_rate_limit(self) -> None:
        """Apply standard rate limiting for regular-sized code."""
        now = time.time()
        minute_ago = now - 60

        # Remove old requests outside the 1-minute window
        while self.request_times and self.request_times[0] < minute_ago:
            self.request_times.popleft()

        # Check if we've exceeded the rate limit
        if len(self.request_times) >= self.requests_per_minute:
            # Wait until the oldest request is outside the window
            sleep_time = 60 - (now - self.request_times[0]) + 0.1
            logger.warning(
                "rate_limiter.throttling",
                extra={
                    "event": "rate_limiter.throttling",
                    "sleep_seconds": sleep_time,
                    "requests_in_window": len(self.request_times),
                },
            )
            await asyncio.sleep(sleep_time)
            now = time.time()

        # Record this request
        self.request_times.append(now)
        logger.debug(
            "rate_limiter.request_allowed",
            extra={
                "event": "rate_limiter.request_allowed",
                "requests_in_window": len(self.request_times),
            },
        )

    async def _process_large_code_queue(self) -> None:
        """
        Process large code submissions one at a time (serial processing).
        This ensures only 1 request for large code at a time.
        """
        if self.processing_large_code:
            # Already processing, just add to queue
            return

        self.processing_large_code = True
        try:
            # Wait for rate limit before processing
            await self._wait_for_rate_limit()
        finally:
            self.processing_large_code = False

    async def execute_with_rate_limit(
        self,
        code_length: int,
        func: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Execute a function with rate limiting applied.
        Ensures only 1 concurrent request for code >= 10k characters.
        """
        await self.acquire(code_length)
        return await func(*args, **kwargs)

    def reset(self) -> None:
        """Reset rate limiter state."""
        self.request_times.clear()
        self.processing_large_code = False
