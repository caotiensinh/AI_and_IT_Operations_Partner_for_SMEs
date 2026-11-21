"""Latest Asahi metrics read model.

Only caller-authenticated, RLS tenant-scoped rows may be supplied to this
formatter. Agent collection/enrollment/ingest are not exposed by this module.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID


def asahi_latest_response(tenant_id: UUID, rows: list[tuple]) -> dict:
    devices = []
    for device_id,site_id,hostname,cpu,memory,uptime,sampled_at in rows:
        if sampled_at.tzinfo is None:
            raise ValueError("database samples must be timezone aware")
        devices.append({
            "device_id":str(device_id),
            "site_id":str(site_id),
            "hostname":hostname,
            "cpu_percent":float(cpu) if cpu is not None else None,
            "memory_percent":float(memory) if memory is not None else None,
            "uptime_seconds":uptime,
            "sampled_at":sampled_at.astimezone(timezone.utc).isoformat(),
        })
    return {"tenant_id":str(tenant_id),"devices":devices}
