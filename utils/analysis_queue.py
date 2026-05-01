"""Async analysis queue with controlled concurrency."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar

from utils.logger import get_logger


logger = get_logger(__name__)
T = TypeVar("T")


class QueueStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class QueueTask:
    task_id: str
    coro_factory: Callable[..., Awaitable[T]]
    args: tuple[Any, ...] = field(default_factory=tuple)
    kwargs: dict[str, Any] = field(default_factory=dict)
    future: asyncio.Future[T] | None = None
    status: QueueStatus = QueueStatus.QUEUED
    result: Optional[T] = None
    error: Optional[str] = None


class AnalysisQueue:
    def __init__(self, worker_count: int = 1, cooldown_seconds: float = 0.0):
        self.worker_count = max(1, worker_count)
        self.cooldown_seconds = max(0.0, cooldown_seconds)
        self._queue: asyncio.Queue[QueueTask] = asyncio.Queue()
        self._tasks: Dict[str, QueueTask] = {}
        self._running = False
        self._worker_tasks: list[asyncio.Task[Any]] = []

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._worker_tasks = [asyncio.create_task(self._worker(i + 1)) for i in range(self.worker_count)]
        logger.info("analysis_queue.started", extra={"workers": self.worker_count})

    async def stop(self) -> None:
        self._running = False
        for task in self._worker_tasks:
            task.cancel()
        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        logger.info("analysis_queue.stopped")

    async def submit(self, coro_factory: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
        if not self._running:
            await self.start()

        loop = asyncio.get_running_loop()
        future: asyncio.Future[T] = loop.create_future()
        task = QueueTask(
            task_id=str(uuid.uuid4()),
            coro_factory=coro_factory,
            args=args,
            kwargs=kwargs,
            future=future,
        )
        self._tasks[task.task_id] = task
        await self._queue.put(task)

        logger.info(
            "analysis_queue.enqueued",
            extra={"task_id": task.task_id, "queue_depth": self._queue.qsize()},
        )
        return await future

    async def _worker(self, worker_id: int) -> None:
        while self._running:
            try:
                task = await asyncio.wait_for(self._queue.get(), timeout=0.25)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            task.status = QueueStatus.PROCESSING
            logger.info(
                "analysis_queue.processing",
                extra={"task_id": task.task_id, "worker_id": worker_id},
            )

            try:
                result = await task.coro_factory(*task.args, **task.kwargs)
                task.result = result
                task.status = QueueStatus.COMPLETED
                if task.future and not task.future.done():
                    task.future.set_result(result)
                logger.info(
                    "analysis_queue.completed",
                    extra={"task_id": task.task_id, "worker_id": worker_id},
                )
            except Exception as exc:  # pragma: no cover - surfaced to caller
                task.error = str(exc)
                task.status = QueueStatus.FAILED
                if task.future and not task.future.done():
                    task.future.set_exception(exc)
                logger.error(
                    "analysis_queue.failed",
                    extra={"task_id": task.task_id, "worker_id": worker_id, "error": task.error},
                )
            finally:
                self._queue.task_done()
                if self.cooldown_seconds > 0:
                    await asyncio.sleep(self.cooldown_seconds)

    def stats(self) -> dict[str, int]:
        queued = sum(1 for task in self._tasks.values() if task.status == QueueStatus.QUEUED)
        processing = sum(1 for task in self._tasks.values() if task.status == QueueStatus.PROCESSING)
        completed = sum(1 for task in self._tasks.values() if task.status == QueueStatus.COMPLETED)
        failed = sum(1 for task in self._tasks.values() if task.status == QueueStatus.FAILED)
        return {
            "queued": queued,
            "processing": processing,
            "completed": completed,
            "failed": failed,
            "queue_depth": self._queue.qsize(),
        }


_queue_instance: AnalysisQueue | None = None


def get_analysis_queue(worker_count: int = 1, cooldown_seconds: float = 0.0) -> AnalysisQueue:
    global _queue_instance
    if _queue_instance is None:
        _queue_instance = AnalysisQueue(worker_count=worker_count, cooldown_seconds=cooldown_seconds)
    return _queue_instance
