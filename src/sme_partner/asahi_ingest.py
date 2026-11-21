"""Trusted read-only poll -> separate credential-bound Postgres ingestion.

No HTTP endpoint, scheduler or public enrollment API. Credentials and bindings
are supplied exclusively by a future privileged operator/secret store.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import re
from uuid import UUID
from collections.abc import Callable

from .adapters.asahi import DeviceBinding, NormalizedTelemetry
from .adapters.asahi_https import AsahiHTTPSPoller


@dataclass(frozen=True,slots=True)
class IngestAuthorization:
    enrollment_id: UUID
    credential: str
    binding: DeviceBinding

    def __post_init__(self):
        if not isinstance(self.enrollment_id,UUID) or self.enrollment_id.int==0:
            raise ValueError("invalid enrollment id")
        if not isinstance(self.credential,str) or not re.fullmatch(r"[A-Za-z0-9_-]{43,128}",self.credential):
            raise ValueError("invalid enrollment credential")
        if not isinstance(self.binding, DeviceBinding):
            raise ValueError("trusted enrollment binding required")


def ingest_one(poller: AsahiHTTPSPoller, connect: Callable, auth: IngestAuthorization,
               observed_at: datetime) -> bool:
    """Uses a distinct ingest-only DB login; returns False for duplicate/rejected."""
    sample: NormalizedTelemetry=poller.poll(observed_at)
    if (sample.tenant_id,sample.site_id,sample.device_id) != (auth.binding.tenant_id,auth.binding.site_id,auth.binding.device_id):
        raise ValueError("agent binding differs from trusted enrollment")
    credential_digest=hashlib.sha256(auth.credential.encode("ascii")).digest()
    with connect() as conn:
        with conn.transaction():
            # The connection MUST be the dedicated ingest login or an isolated
            # CI principal allowed to assume sme_ingest; never the web runtime.
            conn.execute("SET LOCAL ROLE sme_ingest")
            return bool(conn.execute(
                "SELECT sme.ingest_asahi_sample(%s,%s,%s,%s,%s::numeric,%s::numeric,%s::bigint)",
                (auth.enrollment_id,credential_digest,sample.sampled_at,
                 sample.hostname,sample.cpu_percent,sample.memory_percent,
                 sample.uptime_seconds),
            ).fetchone()[0])
