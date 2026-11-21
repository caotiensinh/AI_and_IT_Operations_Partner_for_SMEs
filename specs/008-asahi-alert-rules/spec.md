# Spec 008 — Tenant-scoped Asahi alert rule kernel

## Goal
Convert authorized, normalized CPU/RAM samples to deterministic alert
transitions without sending notifications or exposing other tenants' state.

## Acceptance
- Two consecutive samples at/above threshold trigger an alert once.
- Triggered alerts do not repeat while elevated.
- Clear only after metric falls below threshold by a configured margin.
- State keys include tenant, site, device and metric.
- Duplicate/out-of-order samples ignored; missing sensors never interpreted as 0.
- Invalid values and policy are denied; bounded in-memory state fails closed.
- All Python and existing PostgreSQL/Chromium/staging regressions PASS.

## Explicit exclusions
No cross-process state, persistent alert history, alert persistence or dedup
across restarts, email/SMS/webhook sending, escalation, customer policies UI,
alert scheduling, device outage detection or production delivery.
