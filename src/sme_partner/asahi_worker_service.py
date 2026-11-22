"""Supervised Asahi worker loop with bounded failures and safe shutdown.

No hardware discovery or secret loading occurs in this module. A privileged
process must supply an approved, tenant-bound tick callable externally.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from collections.abc import Callable
import time


@dataclass(frozen=True, slots=True)
class WorkerLoopPolicy:
    interval_seconds: float = 30
    retry_delay_seconds: float = 5
    max_consecutive_failures: int = 5

    def __post_init__(self) -> None:
        for value in (self.interval_seconds, self.retry_delay_seconds):
            if type(value) not in (float, int) or not 0.1 <= value <= 3600:
                raise ValueError("invalid worker loop interval")
        if type(self.max_consecutive_failures) is not int or not 1 <= self.max_consecutive_failures <= 20:
            raise ValueError("invalid maximum consecutive failures")


@dataclass(frozen=True, slots=True)
class WorkerSnapshot:
    state: str
    completed_ticks: int
    failed_ticks: int
    consecutive_failures: int
    last_outcome: str | None


class WorkerLoopExhausted(RuntimeError):
    """Supervisor must investigate or restart after bounded consecutive failures."""


class AsahiWorkerLoop:
    def __init__(
        self,
        tick: Callable[[], str],
        *,
        policy: WorkerLoopPolicy = WorkerLoopPolicy(),
        on_snapshot: Callable[[WorkerSnapshot], None] | None = None,
        retryable: tuple[type[Exception], ...] = (TimeoutError, ConnectionError),
    ) -> None:
        self.tick=tick
        self.policy=policy
        self.on_snapshot=on_snapshot
        self.retryable=retryable
        self._snapshot=WorkerSnapshot("created",0,0,0,None)
        self._running=False

    @property
    def snapshot(self) -> WorkerSnapshot:
        return self._snapshot

    def _report(self, state: str, *, completed: int | None = None,
                failed: int | None = None, consecutive: int | None = None,
                outcome: str | None = None) -> None:
        old=self._snapshot
        self._snapshot=WorkerSnapshot(
            state,
            old.completed_ticks if completed is None else completed,
            old.failed_ticks if failed is None else failed,
            old.consecutive_failures if consecutive is None else consecutive,
            old.last_outcome if outcome is None else outcome,
        )
        if self.on_snapshot:
            self.on_snapshot(self._snapshot)

    def run(self, stop: Event) -> WorkerSnapshot:
        """Blocking loop. Call with a dedicated process supervisor thread.

        Uses stop.wait() rather than sleep() for immediate shutdown.
        Only known transient failures are retried; unexpected exceptions
        propagate and are not silently converted to healthy status.
        No exception messages, tokens or endpoint URLs enter snapshots.
        """
        if self._running:
            raise RuntimeError("worker loop already running")
        self._running=True
        self._report("running")
        try:
            while not stop.is_set():
                try:
                    outcome=self.tick()
                    if outcome not in ("not_due","inserted","duplicate"):
                        raise ValueError("unexpected worker tick outcome")
                except self.retryable:
                    failures=self._snapshot.consecutive_failures+1
                    self._report("degraded",failed=self._snapshot.failed_ticks+1,
                                 consecutive=failures,outcome="retryable_failure")
                    if failures>=self.policy.max_consecutive_failures:
                        self._report("failed")
                        raise WorkerLoopExhausted("consecutive retry limit reached")
                    if stop.wait(self.policy.retry_delay_seconds):
                        break
                else:
                    self._report("running",completed=self._snapshot.completed_ticks+1,
                                 consecutive=0,outcome=outcome)
                    if stop.wait(self.policy.interval_seconds):
                        break
            self._report("stopped")
            return self._snapshot
        except Exception:
            if self._snapshot.state!="failed":
                self._report("failed")
            raise
        finally:
            self._running=False
