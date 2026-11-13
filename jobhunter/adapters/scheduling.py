"""Scheduling adapters — lock-file lease, cadences, jitter, per-host budget, circuit breaker.

Pure scheduling primitives with no business logic. Used by the scheduler worker.
"""

from __future__ import annotations

import json
import logging
import os
import random
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


class LockFileLease:
    """Single-writer lock-file lease.

    Only one scheduler instance can hold the lease at a time.
    Uses os.O_CREAT | os.O_EXCL for cross-platform exclusive file creation
    (works on both Windows and Unix). Stale locks are forcibly taken over.
    """

    def __init__(self, path: str | Path = "data/scheduler.lock", ttl_seconds: int = 300):
        self.path = Path(path)
        self.ttl_seconds = ttl_seconds
        self._owned = False

    def acquire(self) -> bool:
        """Try to acquire the lease. Returns True if held, False if locked by another."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            # O_CREAT | O_EXCL fails if the file already exists (cross-platform)
            fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o644)
            os.close(fd)
            self._write_owner()
            self._owned = True
            return True
        except FileExistsError:
            # Lock exists — check if stale
            try:
                content = self.path.read_text(encoding="utf-8")
                owner = json.loads(content)
                last = owner.get("last_heartbeat", 0)
                if time.time() - last > self.ttl_seconds:
                    # Stale — remove and re-acquire
                    self.path.unlink(missing_ok=True)
                    return self.acquire()
            except (OSError, ValueError):
                # Corrupt lock file — remove and re-acquire
                self.path.unlink(missing_ok=True)
                return self.acquire()
            return False

    def release(self) -> None:
        """Release the lease."""
        if self._owned:
            try:
                self.path.unlink(missing_ok=True)
            except OSError:
                pass
            self._owned = False

    def heartbeat(self) -> None:
        """Update the heartbeat timestamp."""
        if self._owned:
            self._write_owner()

    def _write_owner(self) -> None:
        try:
            self.path.write_text(
                json.dumps({"pid": os.getpid(), "last_heartbeat": time.time()}),
                encoding="utf-8",
            )
        except OSError:
            pass


@dataclass
class SourceCadence:
    """Per-source cadence configuration."""

    source: str
    min_interval_seconds: int = 3600
    max_daily_requests: int = 100
    jitter_seconds: int = 60


class CadenceManager:
    """Tracks per-source last-run times and enforces cadences."""

    def __init__(self, state_path: str | Path = "data/scheduler_state.json"):
        self.path = Path(state_path)
        self.state: dict[str, float] = {}
        self.daily_counts: dict[str, int] = {}
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.state = data.get("last_run", {})
            self.daily_counts = data.get("daily_counts", {})
        except (OSError, ValueError):
            self.state = {}
            self.daily_counts = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".scheduler_state_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(
                    {"last_run": self.state, "daily_counts": self.daily_counts},
                    f,
                )
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def remaining(self, source: str, cadence: SourceCadence) -> int:
        """Seconds until the source can be run again (0 if ready)."""
        now = time.time()
        last = self.state.get(source, 0)
        elapsed = now - last
        remaining = cadence.min_interval_seconds - elapsed
        if remaining > 0:
            return int(remaining)

        # Check daily budget
        today = str(int(now // 86400))
        key = f"{source}:{today}"
        used = self.daily_counts.get(key, 0)
        if used >= cadence.max_daily_requests:
            return int(86400 - (now % 86400))  # seconds until tomorrow

        return 0

    def mark(self, source: str, cadence: SourceCadence) -> None:
        """Record that the source was run."""
        now = time.time()
        self.state[source] = now
        today = str(int(now // 86400))
        key = f"{source}:{today}"
        self.daily_counts[key] = self.daily_counts.get(key, 0) + 1
        self._save()

    def jitter_delay(self, cadence: SourceCadence) -> float:
        """Return a random jitter delay in seconds."""
        return random.uniform(0, cadence.jitter_seconds)


@dataclass
class CircuitState:
    """Circuit breaker state for a source."""

    failures: int = 0
    last_failure: float = 0.0
    open_until: float = 0.0


class CircuitBreaker:
    """Circuit breaker: opens on repeated 401/403/429, stops issuing requests."""

    def __init__(self, threshold: int = 5, cooldown_seconds: int = 300):
        self.threshold = threshold
        self.cooldown_seconds = cooldown_seconds
        self.states: dict[str, CircuitState] = {}

    def is_open(self, source: str) -> bool:
        state = self.states.get(source)
        if state is None:
            return False
        if time.time() > state.open_until:
            # Half-open: allow one trial request
            return False
        return True

    def record_success(self, source: str) -> None:
        if source in self.states:
            del self.states[source]

    def record_failure(self, source: str, status_code: int | None = None) -> None:
        """Record a failure. Open the circuit if threshold reached."""
        now = time.time()
        state = self.states.get(source, CircuitState())
        state.failures += 1
        state.last_failure = now

        if status_code in (401, 403, 429):
            # Auth/rate-limit failures count double
            state.failures += 1

        if state.failures >= self.threshold:
            state.open_until = now + self.cooldown_seconds
            logger.warning(
                f"Circuit breaker OPEN for {source} "
                f"(failures={state.failures}, cooldown={self.cooldown_seconds}s)"
            )

        self.states[source] = state


class PerHostBudget:
    """Per-host request budget to avoid hammering a single host."""

    def __init__(self, max_per_minute: int = 60):
        self.max_per_minute = max_per_minute
        self.timestamps: dict[str, list[float]] = {}

    def can_proceed(self, host: str) -> bool:
        now = time.time()
        window_start = now - 60
        times = self.timestamps.get(host, [])
        # Prune old entries
        times = [t for t in times if t > window_start]
        self.timestamps[host] = times
        return len(times) < self.max_per_minute

    def record(self, host: str) -> None:
        now = time.time()
        self.timestamps.setdefault(host, []).append(now)
