"""Read-only ASAHI metric normalization; deliberately no network or hardware writes.

Source contract from caotiensinh/ubuntu_asahi_server, agent/asahi_agent.py
and control_center/agent.py. No source code or credentials copied.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any
from uuid import UUID


class MetricRejected(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DeviceBinding:
    tenant_id: UUID
    site_id: UUID
    device_id: UUID
    # A binding must be supplied by a future trusted device-enrollment service.
    # Never derive IDs from an agent hostname, request JSON or self-reported token.


@dataclass(frozen=True, slots=True)
class NormalizedTelemetry:
    tenant_id: UUID
    site_id: UUID
    device_id: UUID
    sampled_at: datetime
    hostname: str
    cpu_percent: float | None
    memory_percent: float | None
    uptime_seconds: int | None
    disk_mounts: tuple[tuple[str, float | None], ...]


def _percent(value: Any, field: str) -> float | None:
    if value is None:
        return None
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100:
        raise MetricRejected(f"invalid {field}")
    return round(float(value), 2)


def normalize_asahi_snapshot(
    *,
    payload: dict[str, Any],
    binding: DeviceBinding,
    observed_at: datetime,
    maximum_clock_skew_seconds: int = 300,
) -> NormalizedTelemetry:
    """Accept limited, known metrics; unknown fields/metadata are discarded.

    IMPORTANT: This function does not authenticate the agent. The device
    binding must be resolved and authorized before it is invoked.
    """
    if not isinstance(binding, DeviceBinding) or not all(
        isinstance(v, UUID) for v in (binding.tenant_id,binding.site_id,binding.device_id)
    ):
        raise MetricRejected("invalid device binding")
    if not isinstance(payload, dict):
        raise MetricRejected("invalid telemetry payload")
    if observed_at.tzinfo is None:
        raise MetricRejected("observed time must include timezone")
    observed_at=observed_at.astimezone(timezone.utc)
    raw_time=payload.get("timestamp",payload.get("time"))
    if type(raw_time) is not int or not 0 < raw_time < 2**42:
        raise MetricRejected("missing or invalid timestamp")
    sampled_at=datetime.fromtimestamp(raw_time,tz=timezone.utc)
    if maximum_clock_skew_seconds < 0 or abs((observed_at-sampled_at).total_seconds()) > maximum_clock_skew_seconds:
        raise MetricRejected("stale or future telemetry")
    hostname=payload.get("hostname")
    if not isinstance(hostname,str) or not 1 <= len(hostname) <= 128 or any(
        ord(ch) < 32 or ord(ch) == 127 for ch in hostname
    ):
        raise MetricRejected("invalid hostname")
    cpu=_percent(payload.get("cpu_pct"),"cpu_pct")
    memory=_percent(payload.get("memory_pct"),"memory_pct")
    raw_uptime=payload.get("uptime_s")
    if raw_uptime is not None and (type(raw_uptime) is not int or not 0 <= raw_uptime <= 10**10):
        raise MetricRejected("invalid uptime_s")
    disks=payload.get("disks",[])
    if not isinstance(disks,list) or len(disks)>32:
        raise MetricRejected("invalid disks")
    mounts=[]
    seen=set()
    for disk in disks:
        if not isinstance(disk,dict):
            raise MetricRejected("invalid disk entry")
        mount=disk.get("mount")
        if not isinstance(mount,str) or not 1 <= len(mount) <= 255 or any(ord(c)<32 for c in mount):
            raise MetricRejected("invalid disk mount")
        if mount in seen:
            raise MetricRejected("duplicate disk mount")
        seen.add(mount)
        mounts.append((mount,_percent(disk.get("used_pct"),"disk.used_pct")))
    return NormalizedTelemetry(
        tenant_id=binding.tenant_id,
        site_id=binding.site_id,
        device_id=binding.device_id,
        sampled_at=sampled_at,
        hostname=hostname,
        cpu_percent=cpu,
        memory_percent=memory,
        uptime_seconds=raw_uptime,
        disk_mounts=tuple(mounts),
    )
