# Spec 009 — Durable Asahi alert state + transactional outbox

## Business outcome
An authenticated ingest worker can evaluate an **existing** telemetry sample
into durable alert transitions. Restarting the process or running a second
worker does not duplicate an alert. No external notifications are sent.

## Acceptance
- Separate tenant/site/device/metric alert state in PostgreSQL.
- Sample provenance from active enrollment credential; no caller-supplied
  tenant, site, device, CPU or RAM value.
- Hysteresis: 90% triggered after two consecutive distinct observations,
  cleared only at or below 80%. No repeated event while elevated.
- NULL sensors ignored, older/equal timestamps ignored.
- `SELECT ... FOR UPDATE` serializes concurrent updates on the same key.
- Insertion of outbox and state change occurs in one transaction.
- Unique outbox key guarantees idempotency across restarts.
- No app/ingest direct SELECT/INSERT/UPDATE/DELETE on outbox/state.
- No web/auth principal may call the evaluation function.
- Positive/negative real PostgreSQL tests, existing smoke/Chromium PASS.

## Explicit exclusions
No outbox delivery workers, alert acknowledgements, tenant-configurable
thresholds, retention policy, external email/SMS/webhook, production
distributed scheduling or hardware integration. Outbox events are **pending**
records, not notifications delivered to customers.
