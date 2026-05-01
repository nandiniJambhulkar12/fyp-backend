"""Request queue and worker system for handling concurrent analysis requests."""

import asyncio
import uuid
from dataclasses import dataclass
from typing import Dict, Optional, Callable, Any
from enum import Enum
from utils.logger import get_logger

logger = get_logger(__name__)


class RequestStatus(str, Enum):
    """Status of a queued request."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class QueuedRequest:
    """A request waiting to be processed."""
    request_id: str
    func: Callable
    args: tuple
    kwargs: dict
    status: RequestStatus = RequestStatus.QUEUED
    result: Optional[Any] = None
    error: Optional[str] = None

    async def execute(self) -> None:
        """Execute the request function."""
        self.status = RequestStatus.PROCESSING
        try:
            self.result = await self.func(*self.args, **self.kwargs)
            self.status = RequestStatus.COMPLETED
            logger.info(
                "queue.request_completed",
                extra={"request_id": self.request_id},
            )
        except Exception as exc:
            self.error = str(exc)
            self.status = RequestStatus.FAILED
            logger.error(
                "queue.request_failed",
                extra={
                    "request_id": self.request_id,
                    "error": self.error,
                },
            )


class RequestQueue:
    """Async request queue with worker pool."""

    def __init__(self, max_concurrent_workers: int = 3):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.max_workers = max_concurrent_workers
        self.requests: Dict[str, QueuedRequest] = {}
        self.workers_running = False

    async def add_request(
        self,
        func: Callable,
        *args,
        request_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Add a request to the queue.

        Args:
            func: Async function to execute
            *args: Positional arguments
            request_id: Optional custom request ID
            **kwargs: Keyword arguments

        Returns:
            Request ID
        """
        req_id = request_id or str(uuid.uuid4())
        request = QueuedRequest(
            request_id=req_id,
            func=func,
            args=args,
            kwargs=kwargs,
        )

        self.requests[req_id] = request
        await self.queue.put(request)

        logger.debug(
            "queue.request_added",
            extra={
                "request_id": req_id,
                "queue_size": self.queue.qsize(),
            },
        )

        return req_id

    async def get_request_status(self, request_id: str) -> Optional[QueuedRequest]:
        """Get request status and result."""
        return self.requests.get(request_id)

    async def worker(self, worker_id: int) -> None:
        """Process requests from queue."""
        while self.workers_running:
            try:
                # Wait for request or check every 100ms
                request = await asyncio.wait_for(
                    self.queue.get(),
                    timeout=0.1
                )
                logger.debug(
                    "queue.worker_processing",
                    extra={
                        "worker_id": worker_id,
                        "request_id": request.request_id,
                    },
                )
                await request.execute()

            except asyncio.TimeoutError:
                # No request available, loop continues
                continue
            except Exception as exc:
                logger.error(
                    "queue.worker_error",
                    extra={
                        "worker_id": worker_id,
                        "error": str(exc),
                    },
                )

    async def start(self) -> None:
        """Start worker pool."""
        if self.workers_running:
            return

        self.workers_running = True
        logger.info(
            "queue.workers_started",
            extra={"num_workers": self.max_workers},
        )

        # Create worker tasks
        self.worker_tasks = [
            asyncio.create_task(self.worker(i))
            for i in range(self.max_workers)
        ]

    async def stop(self) -> None:
        """Stop worker pool gracefully."""
        self.workers_running = False
        if hasattr(self, 'worker_tasks'):
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        logger.info("queue.workers_stopped")

    def get_queue_stats(self) -> dict:
        """Get current queue statistics."""
        completed = sum(
            1 for r in self.requests.values()
            if r.status == RequestStatus.COMPLETED
        )
        failed = sum(
            1 for r in self.requests.values()
            if r.status == RequestStatus.FAILED
        )
        processing = sum(
            1 for r in self.requests.values()
            if r.status == RequestStatus.PROCESSING
        )
        queued = sum(
            1 for r in self.requests.values()
            if r.status == RequestStatus.QUEUED
        )

        return {
            "total_requests": len(self.requests),
            "queued": queued,
            "processing": processing,
            "completed": completed,
            "failed": failed,
            "queue_depth": self.queue.qsize(),
        }
