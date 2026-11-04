"""Bounded in-process jobs for public-web research.

Job progress is ephemeral; an optional completion hook persists the result.
No exception, API key, or raw provider response is exposed.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any, Callable
from uuid import uuid4

from app.intelligence.openai_client import InvalidOpenAIJSONError, MissingOpenAIKeyError, OpenAIRequestError


class JobQueueFull(Exception):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, MissingOpenAIKeyError):
        return "The configured research provider API key is not available on the backend."
    if isinstance(exc, InvalidOpenAIJSONError):
        return "The model returned an invalid or ungrounded response. Please retry."
    if isinstance(exc, OpenAIRequestError):
        return "The model request failed. Check API access, quota and network, then retry."
    return "Research could not be completed. Please retry."


class ResearchJobManager:
    """Thread-safe capacity limit, queue, progress and time-bound results."""

    def __init__(self, research: Callable[..., Any], *, workers: int = 2,
                 capacity: int = 6, ttl_seconds: float = 1800, history_capacity: int = 100,
                 on_success: Callable[..., int] | None = None):
        if workers < 1 or capacity < workers or ttl_seconds <= 0 or history_capacity < 1:
            raise ValueError("Invalid research job limits")
        self._research = research
        self._on_success = on_success
        self._capacity = capacity
        self._ttl_seconds = ttl_seconds
        self._history_capacity = history_capacity
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="misi-research")
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}

    def _evict_expired(self) -> None:
        now = time.monotonic()
        for job_id, job in list(self._jobs.items()):
            if job["_expires"] is not None and job["_expires"] <= now:
                del self._jobs[job_id]
        completed = sorted((job for job in self._jobs.values() if job["_expires"] is not None),
                           key=lambda job: job["_expires"])
        # Retain a bounded amount of finished output even at high request rates.
        for job in completed[:max(0, len(completed) - self._history_capacity)]:
            del self._jobs[job["job_id"]]

    def submit(self, request: Any) -> dict[str, Any]:
        with self._lock:
            self._evict_expired()
            active = sum(job["status"] in {"queued", "running"} for job in self._jobs.values())
            if active >= self._capacity:
                raise JobQueueFull()
            job_id = str(uuid4())
            self._jobs[job_id] = {
                "job_id": job_id, "status": "queued", "created_at": _now(),
                "started_at": None, "finished_at": None,
                "progress": {"phase": "queued", "planned": 0, "completed": 0, "failed": 0, "active_queries": []},
                "result": None, "error": None, "saved_run_id": None, "save_error": None, "_expires": None,
            }
            try:
                self._executor.submit(self._run, job_id, request)
            except Exception:
                del self._jobs[job_id]
                raise
            return self._snapshot(self._jobs[job_id])

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._evict_expired()
            job = self._jobs.get(job_id)
            return self._snapshot(job) if job else None

    @staticmethod
    def _snapshot(job: dict[str, Any]) -> dict[str, Any]:
        # Progress is mutated under the lock, so copy the nested mutable values.
        return {key: (dict(value, active_queries=list(value["active_queries"])) if key == "progress" else value)
                for key, value in job.items() if not key.startswith("_")}

    def _progress(self, job_id: str, update: dict[str, Any]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job["status"] != "running":
                return
            current = job["progress"]
            phase = update.get("phase")
            if phase in {"planning", "searching", "synthesising", "completed"}:
                current["phase"] = phase
            for name in ("planned", "completed", "failed"):
                value = update.get(name)
                if isinstance(value, int) and not isinstance(value, bool):
                    current[name] = max(0, min(value, 12))
            queries = update.get("active_queries")
            if isinstance(queries, list):
                current["active_queries"] = [q[:600] for q in queries[:3] if isinstance(q, str)]

    def _run(self, job_id: str, request: Any) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job["status"] = "running"
            job["started_at"] = _now()
            job["progress"]["phase"] = "planning"
        result = None
        error = None
        save_error = None
        saved_run_id = None
        finished_at = None
        try:
            result = self._research(request, progress_callback=lambda update: self._progress(job_id, update))
            if hasattr(result, "model_dump"):
                result = result.model_dump(mode="json")
            finished_at = _now()
            if self._on_success is not None:
                try:
                    saved_run_id = self._on_success(job_id, result, finished_at)
                except Exception:
                    # Keep the completed result available for an explicit retry.
                    save_error = "Could not save this research. Please retry saving it."
        except Exception as exc:
            error = _safe_error(exc)
        finally:
            with self._lock:
                job = self._jobs[job_id]
                job["result"] = result if error is None else None
                job["error"] = error
                job["saved_run_id"] = saved_run_id
                job["save_error"] = save_error
                job["status"] = "completed" if error is None else "failed"
                if error is None:
                    job["progress"]["phase"] = "completed"
                job["progress"]["active_queries"] = []
                job["finished_at"] = finished_at or _now()
                job["_expires"] = time.monotonic() + self._ttl_seconds

    def shutdown(self) -> None:
        """Allow deterministic test cleanup; does not cancel running work."""
        self._executor.shutdown(wait=True)
