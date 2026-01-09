"""Lightweight in-process background task queue."""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
import threading
import uuid
from typing import Any, Callable, Dict, Optional

from flask import current_app


@dataclass
class BackgroundJob:
    """Simple handle for queued work."""

    id: str
    future: Future

    @property
    def done(self) -> bool:
        return self.future.done()

    def result(self, timeout: Optional[float] = None) -> Any:
        return self.future.result(timeout=timeout)

    def exception(self, timeout: Optional[float] = None) -> Optional[BaseException]:
        return self.future.exception(timeout=timeout)


class BackgroundTaskQueue:
    """Execute callables on a small worker pool within the Flask app context."""

    def __init__(self, max_workers: int = 2):
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="bg-task")
        self._jobs: Dict[str, BackgroundJob] = {}
        self._lock = threading.Lock()

    def enqueue(self, func: Callable[..., Any], *args, **kwargs) -> BackgroundJob:
        app = current_app._get_current_object()
        job_id = uuid.uuid4().hex

        def runner():
            with app.app_context():
                return func(*args, **kwargs)

        future = self._executor.submit(runner)
        job = BackgroundJob(id=job_id, future=future)
        with self._lock:
            self._jobs[job_id] = job
        future.add_done_callback(lambda _future, job_id=job_id: self._cleanup(job_id))
        return job

    def get_job(self, job_id: str) -> Optional[BackgroundJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def _cleanup(self, job_id: str) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)
