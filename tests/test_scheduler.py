"""
Unit tests for the scheduler service (WP-02-05).
"""
from __future__ import annotations

import time

from jobhunter.adapters.scheduling import (
    LockFileLease,
    SourceCadence,
    CadenceManager,
    CircuitBreaker,
    PerHostBudget,
)
from jobhunter.app.result import Err, Ok, is_err, is_ok
from jobhunter.app.services.scheduler import SchedulerService


class TestLockFileLease:
    def test_acquire_and_release(self, tmp_path):
        lock = tmp_path / "test.lock"
        lease = LockFileLease(str(lock), ttl_seconds=60)
        assert lease.acquire() is True
        assert lease.acquire() is False  # already held
        lease.release()
        assert lease.acquire() is True  # can re-acquire after release
        lease.release()

    def test_stale_lock_takeover(self, tmp_path):
        lock = tmp_path / "test.lock"
        lock.write_text('{"pid": 99999, "last_heartbeat": 0}', encoding="utf-8")
        lease = LockFileLease(str(lock), ttl_seconds=60)
        assert lease.acquire() is True
        lease.release()


class TestCadenceManager:
    def test_remaining_zero_when_never_run(self, tmp_path):
        state = tmp_path / "state.json"
        mgr = CadenceManager(str(state))
        cadence = SourceCadence(source="feed1", min_interval_seconds=3600)
        assert mgr.remaining("feed1", cadence) == 0

    def test_remaining_positive_after_run(self, tmp_path):
        state = tmp_path / "state.json"
        mgr = CadenceManager(str(state))
        cadence = SourceCadence(source="feed1", min_interval_seconds=3600)
        mgr.mark("feed1", cadence)
        remaining = mgr.remaining("feed1", cadence)
        assert remaining > 0
        assert remaining <= 3600

    def test_daily_budget(self, tmp_path):
        state = tmp_path / "state.json"
        mgr = CadenceManager(str(state))
        cadence = SourceCadence(source="feed1", min_interval_seconds=0, max_daily_requests=2)
        mgr.mark("feed1", cadence)
        mgr.mark("feed1", cadence)
        remaining = mgr.remaining("feed1", cadence)
        assert remaining > 0  # daily budget exhausted


class TestCircuitBreaker:
    def test_opens_after_threshold(self):
        # 429 counts double, so 2 failures with 429 = 4 failure points >= threshold 3
        cb = CircuitBreaker(threshold=3, cooldown_seconds=60)
        assert cb.is_open("src1") is False
        cb.record_failure("src1", 429)  # failures = 2
        assert cb.is_open("src1") is False
        cb.record_failure("src1", 429)  # failures = 4 >= 3 -> OPEN
        assert cb.is_open("src1") is True

    def test_closes_after_cooldown(self):
        cb = CircuitBreaker(threshold=5, cooldown_seconds=0)
        cb.record_failure("src1", 429)  # failures = 2 < 5, not open
        cb.record_failure("src1", 429)  # failures = 4 < 5, not open
        cb.record_failure("src1", 429)  # failures = 6 >= 5 -> OPEN
        assert cb.is_open("src1") is True
        cb.record_success("src1")
        assert cb.is_open("src1") is False

    def test_success_closes_circuit(self):
        cb = CircuitBreaker(threshold=2, cooldown_seconds=60)
        cb.record_failure("src1", 429)  # failures = 2 >= 2 -> OPEN
        assert cb.is_open("src1") is True
        cb.record_success("src1")
        assert cb.is_open("src1") is False


class TestPerHostBudget:
    def test_allows_under_limit(self):
        budget = PerHostBudget(max_per_minute=3)
        assert budget.can_proceed("example.com") is True
        budget.record("example.com")
        budget.record("example.com")
        assert budget.can_proceed("example.com") is True

    def test_blocks_at_limit(self):
        budget = PerHostBudget(max_per_minute=2)
        budget.record("example.com")
        budget.record("example.com")
        assert budget.can_proceed("example.com") is False


class TestSchedulerService:
    def test_acquire_release_lease(self, tmp_path):
        lock = tmp_path / "scheduler.lock"
        state = tmp_path / "state.json"
        svc = SchedulerService(lock_path=str(lock), state_path=str(state))
        result = svc.start()
        assert is_ok(result)
        svc.stop()

    def test_lease_prevents_double_start(self, tmp_path):
        lock = tmp_path / "scheduler.lock"
        state = tmp_path / "state.json"
        svc1 = SchedulerService(lock_path=str(lock), state_path=str(state))
        svc2 = SchedulerService(lock_path=str(lock), state_path=str(state))
        assert is_ok(svc1.start())
        assert is_err(svc2.start())
        svc1.stop()

    def test_can_run_source_ready(self, tmp_path):
        lock = tmp_path / "scheduler.lock"
        state = tmp_path / "state.json"
        svc = SchedulerService(lock_path=str(lock), state_path=str(state))
        cadence = SourceCadence(source="feed1", min_interval_seconds=3600)
        result = svc.can_run_source("feed1", cadence, "example.com")
        assert is_ok(result)

    def test_can_run_source_cadence(self, tmp_path):
        lock = tmp_path / "scheduler.lock"
        state = tmp_path / "state.json"
        svc = SchedulerService(lock_path=str(lock), state_path=str(state))
        cadence = SourceCadence(source="feed1", min_interval_seconds=3600)
        svc.cadence.mark("feed1", cadence)
        result = svc.can_run_source("feed1", cadence, "example.com")
        assert is_err(result)
        assert result.code == "cadence"

    def test_can_run_source_circuit_open(self, tmp_path):
        lock = tmp_path / "scheduler.lock"
        state = tmp_path / "state.json"
        svc = SchedulerService(lock_path=str(lock), state_path=str(state))
        cadence = SourceCadence(source="feed1", min_interval_seconds=0)
        # Open circuit by recording 3 failures with 429 (each counts double: 3*2=6 >= threshold 5)
        for _ in range(3):
            svc.breaker.record_failure("feed1", 429)
        result = svc.can_run_source("feed1", cadence, "example.com")
        assert is_err(result)
        assert result.code == "circuit_open"
