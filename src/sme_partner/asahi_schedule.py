"""Bounded in-process scheduler for a configured, trusted Asahi ingestion job.

This is an orchestration primitive, not a persistent or distributed scheduler.
Ingest credentials/endpoints never come from HTTP request parameters.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Callable


@dataclass(frozen=True)
class SchedulePolicy:
    interval_seconds: int = 60
    retry_delay_seconds: int = 10
    max_attempts: int = 2

    def __post_init__(self) -> None:
        if not 10 <= self.interval_seconds <= 3600:
            raise ValueError("interval outside operational bounds")
        if not 1 <= self.retry_delay_seconds < self.interval_seconds:
            raise ValueError("retry delay outside operational bounds")
        if not 1 <= self.max_attempts <= 3:
            raise ValueError("too many retry attempts")


@dataclass(frozen=True)
class PollResult:
    outcome: str
    attempts: int
    next_due_monotonic: float


class ScheduledIngest:
    """One process, one enrollment, non-overlapping runs.

    A monotonic time source is injected for repeatable tests. Failed jobs are
    not reported as successful. Retryable failures are explicitly provided
    by the caller; credential/TLS/security errors should not be retryable.
    The job never logs or returns credentials.
    """

    def __init__(
        self,
        action: Callable[[datetime], bool],
        *,
        policy: SchedulePolicy = SchedulePolicy(),
        now_monotonic: Callable[[], float],
        now_utc: Callable[[], datetime],
        retryable: tuple[type[Exception], ...] = (TimeoutError, ConnectionError),
    ):
        self.action = action
        self.policy = policy
        self.now_monotonic = now_monotonic
        self.now_utc = now_utc
        self.retryable = retryable
        self.next_due = 0.0
        self._retry_count = 0
        self._lock = Lock()

    def run_due(self) -> PollResult:
        if not self._lock.acquire(blocking=False):
            return PollResult("busy", 0, self.next_due)
        try:
            current = self.now_monotonic()
            if current < self.next_due:
                return PollResult("not_due", 0, self.next_due)
            attempts = 1
            observed = self.now_utc()
            if observed.tzinfo is None:
                raise ValueError("UTC timestamp must be timezone-aware")
            try:
                inserted = self.action(observed.astimezone(timezone.utc))
                self._retry_count = 0
                outcome = "inserted" if inserted else "duplicate_or_rejected"
            except self.retryable:
                self._retry_count += 1
                if self._retry_count < self.policy.max_attempts:
                    self.next_due = current + self.policy.retry_delay_seconds
                    return PollResult("retry_scheduled", attempts, self.next_due)
                self._retry_count = 0
                outcome = "retry_exhausted"
            except Exception:
                self._retry_count = 0
                self.next_due = current + self.policy.interval_seconds
                raise
            self.next_due = current + self.policy.interval_seconds
            return PollResult(outcome, attempts, self.next_due)
        finally:
            self._lock.release()
