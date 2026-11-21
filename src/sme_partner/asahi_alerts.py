"""Deterministic, tenant-bound Asahi metric alert evaluator.

Decision engine only: no email, no outbound network, no customer-visible
notifications. Persisted alert state and multi-worker coordination are still
required before production delivery.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from uuid import UUID
import math

from .adapters.asahi import NormalizedTelemetry


@dataclass(frozen=True)
class MetricAlertPolicy:
    cpu_critical: float = 90.0
    memory_critical: float = 90.0
    clear_margin: float = 10.0
    consecutive_breaches: int = 2
    max_devices: int = 10000

    def __post_init__(self):
        if any(type(x) not in (float,int) or not math.isfinite(x) or not 1 <= x <= 100
               for x in (self.cpu_critical,self.memory_critical)):
            raise ValueError("critical threshold outside 1..100")
        if type(self.clear_margin) not in (float,int) or not math.isfinite(self.clear_margin) or not 0 < self.clear_margin < min(self.cpu_critical,self.memory_critical):
            raise ValueError("invalid clear margin")
        if type(self.consecutive_breaches) is not int or not 1 <= self.consecutive_breaches <= 10:
            raise ValueError("invalid consecutive sample count")
        if type(self.max_devices) is not int or not 1 <= self.max_devices <= 100000:
            raise ValueError("invalid state cap")


@dataclass(frozen=True)
class AlertDecision:
    tenant_id: UUID
    site_id: UUID
    device_id: UUID
    metric: str
    transition: str
    value: float
    sampled_at: datetime


@dataclass
class _MetricState:
    last_sample_at: datetime | None = None
    breaches: int = 0
    active: bool = False


class AsahiAlertEvaluator:
    def __init__(self, policy: MetricAlertPolicy = MetricAlertPolicy()):
        self.policy = policy
        self._state: dict[tuple[UUID,UUID,UUID,str],_MetricState] = {}
        self._lock = Lock()

    def evaluate(self, sample: NormalizedTelemetry) -> tuple[AlertDecision,...]:
        if not isinstance(sample,NormalizedTelemetry) or sample.sampled_at.tzinfo is None:
            raise ValueError("requires a timezone-aware normalized sample")
        thresholds = {"cpu":self.policy.cpu_critical,"memory":self.policy.memory_critical}
        values = {"cpu":sample.cpu_percent,"memory":sample.memory_percent}
        decisions=[]
        with self._lock:
            # Avoid half-applied updates if state storage is exhausted.
            new_keys=[(sample.tenant_id,sample.site_id,sample.device_id,name)
                      for name,value in values.items()
                      if value is not None and
                      (sample.tenant_id,sample.site_id,sample.device_id,name) not in self._state]
            if len(self._state)+len(new_keys)>self.policy.max_devices*2:
                raise RuntimeError("alert state cap reached; persist/prune before accepting more devices")
            for name,limit in thresholds.items():
                value=values[name]
                if value is None:
                    continue
                if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=100:
                    raise ValueError("invalid normalized metric")
                key=(sample.tenant_id,sample.site_id,sample.device_id,name)
                state=self._state.setdefault(key,_MetricState())
                moment=sample.sampled_at.astimezone(timezone.utc)
                if state.last_sample_at is not None and moment<=state.last_sample_at:
                    continue
                state.last_sample_at=moment
                if state.active:
                    if value<=limit-self.policy.clear_margin:
                        state.active=False
                        state.breaches=0
                        decisions.append(AlertDecision(sample.tenant_id,sample.site_id,sample.device_id,name,"cleared",float(value),moment))
                elif value>=limit:
                    state.breaches+=1
                    if state.breaches>=self.policy.consecutive_breaches:
                        state.active=True
                        decisions.append(AlertDecision(sample.tenant_id,sample.site_id,sample.device_id,name,"triggered",float(value),moment))
                else:
                    state.breaches=0
        return tuple(decisions)
