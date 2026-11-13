"""Scheduler service — single scheduler with lease, cadences, budget, circuit breaker.

Wraps the scheduling adapters with Result[T] error handling.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from jobhunter.adapters.scheduling import (
    CadenceManager,
    CircuitBreaker,
    LockFileLease,
    PerHostBudget,
    SourceCadence,
)
from jobhunter.app.result import Err, Ok, Result

logger = logging.getLogger(__name__)


class SchedulerService:
    """Single scheduler worker with lock-file lease.

    Ensures only one scheduler runs at a time, enforces per-source cadences,
    per-host budgets, and circuit breaker for failed sources.
    """

    def __init__(
        self,
        lock_path: str = "data/scheduler.lock",
        state_path: str = "data/scheduler_state.json",
        ttl_seconds: int = 300,
    ):
        self.lease = LockFileLease(lock_path, ttl_seconds=ttl_seconds)
        self.cadence = CadenceManager(state_path)
        self.breaker = CircuitBreaker()
        self.budget = PerHostBudget()
        self._running = False

    def acquire_lease(self) -> Result[None]:
        """Acquire the single-writer lease. Fails if another scheduler holds it."""
        if self.lease.acquire():
            return Ok(None)
        return Err(error="Another scheduler holds the lease", code="lease_held")

    def release_lease(self) -> None:
        """Release the lease."""
        self.lease.release()

    def heartbeat(self) -> None:
        """Update the lease heartbeat."""
        self.lease.heartbeat()

    def can_run_source(self, source: str, cadence: SourceCadence, host: str) -> Result[None]:
        """Check if a source can be run (cadence, budget, circuit breaker)."""
        if self.breaker.is_open(source):
            return Err(error=f"Circuit breaker open for {source}", code="circuit_open")

        remaining = self.cadence.remaining(source, cadence)
        if remaining > 0:
            return Err(error=f"Cadence not ready for {source} ({remaining}s)", code="cadence")

        if not self.budget.can_proceed(host):
            return Err(error=f"Per-host budget exhausted for {host}", code="budget")

        return Ok(None)

    def mark_source_run(self, source: str, cadence: SourceCadence, host: str, success: bool = True) -> None:
        """Record that a source was run."""
        self.cadence.mark(source, cadence)
        self.budget.record(host)
        if success:
            self.breaker.record_success(source)

    def mark_source_failure(self, source: str, status_code: int | None = None) -> None:
        """Record a source failure (opens circuit breaker on repeated failures)."""
        self.breaker.record_failure(source, status_code)

    async def run_with_lease(
        self,
        source: str,
        cadence: SourceCadence,
        host: str,
        task: Callable,
    ) -> Result:
        """Run a task with lease, cadence, budget, and circuit breaker checks."""
        if not self._running:
            return Err(error="Scheduler not started", code="not_started")

        # Check if we can run
        check = self.can_run_source(source, cadence, host)
        if check.is_err():
            return check

        # Apply jitter
        delay = self.cadence.jitter_delay(cadence)
        if delay > 0:
            await asyncio.sleep(delay)

        # Heartbeat to keep lease alive
        self.heartbeat()

        try:
            result = await task()
            self.mark_source_run(source, cadence, host, success=True)
            return Ok(result)
        except Exception as exc:
            self.mark_source_failure(source, getattr(exc, "status_code", None))
            return Err(error=str(exc), code="task_failed")

    def start(self) -> Result[None]:
        """Start the scheduler (acquire lease)."""
        self._running = True
        return self.acquire_lease()

    def stop(self) -> None:
        """Stop the scheduler (release lease)."""
        self._running = False
        self.release_lease()
