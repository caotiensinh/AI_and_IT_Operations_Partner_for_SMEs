"""One trusted Asahi worker tick using database-backed lease coordination.

This does NOT start a process or schedule background work. One invocation
acquires a lease, calls the existing verified ingest, then records next_due.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from collections.abc import Callable
import hashlib

from .adapters.asahi_https import AsahiHTTPSPoller
from .asahi_ingest import IngestAuthorization, ingest_one


@dataclass(frozen=True,slots=True)
class LeaseTickPolicy:
    lease_seconds: int = 60
    interval_seconds: int = 60
    retry_seconds: int = 10

    def __post_init__(self):
        if not 5 <= self.lease_seconds <= 300:
            raise ValueError("invalid lease duration")
        if not 10 <= self.interval_seconds <= 3600:
            raise ValueError("invalid interval")
        if not 1 <= self.retry_seconds <= 300:
            raise ValueError("invalid retry interval")


def _lease_call(connect: Callable, sql: str, args: tuple) -> bool:
    with connect() as conn:
        with conn.transaction():
            conn.execute("SET LOCAL ROLE sme_ingest")
            return bool(conn.execute(sql,args).fetchone()[0])


def run_leased_ingest_tick(
    *,
    poller: AsahiHTTPSPoller,
    connect: Callable,
    auth: IngestAuthorization,
    worker_id: UUID,
    observed_at: datetime,
    policy: LeaseTickPolicy = LeaseTickPolicy(),
) -> str:
    """Returns 'not_due', 'inserted', or 'duplicate'; errors propagate.

    On poll failure a best-effort completion schedules retry. A failure to
    complete a successful poll is a hard error, never marked success.
    """
    if not isinstance(worker_id,UUID) or worker_id.int==0:
        raise ValueError("invalid worker UUID")
    credential_digest=hashlib.sha256(auth.credential.encode("ascii")).digest()
    granted=_lease_call(
        connect,
        "SELECT sme.try_acquire_asahi_poll(%s,%s,%s,%s)",
        (auth.enrollment_id,credential_digest,worker_id,policy.lease_seconds),
    )
    if not granted:
        return "not_due"

    complete_sql="SELECT sme.complete_asahi_poll(%s,%s,%s,%s,%s,%s)"
    def complete(success: bool) -> bool:
        return _lease_call(
            connect,complete_sql,
            (auth.enrollment_id,credential_digest,worker_id,success,
             policy.interval_seconds,policy.retry_seconds),
        )

    try:
        inserted=ingest_one(poller,connect,auth,observed_at)
    except Exception:
        # Preserve original failure even if completion fails. Expiry still
        # recovers the lease; no secrets or payloads appear in errors here.
        try:
            complete(False)
        except Exception:
            pass
        raise
    if not complete(True):
        raise RuntimeError("ingest lease completion was rejected")
    return "inserted" if inserted else "duplicate"
