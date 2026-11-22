# Spec 011 — Durable polling leases

## Goal
A PostgreSQL-backed lease gate for a trusted Asahi enrollment ensures
that only one worker receives a poll permit per enrolled device at a time.

## Acceptance
- Active enrollment + correct credential digest required to claim or complete.
- No tenant/site ID supplied by caller; lookup is server-side.
- Atomic INSERT...ON CONFLICT conditional UPDATE handles simultaneous claimers.
- Lease has 5–300 second bounded lifetime; expired lease can be recovered.
- Holder alone can complete unexpired lease; success/failure yields different
  bounded next-due intervals (10–3600 s or 1–300 s respectively).
- Revoked enrollment or suspended tenant cannot obtain a lease.
- Direct read/write of lease table denied to ingest/app roles.
- PostgreSQL positive/negative/concurrency tests and all baseline CI PASS.

## Non-goals
No always-on worker, secret-manager binding, leader election, heartbeat
extension, external notifications, actual device polling or customer deployment.
This is a **lease primitive only**, not a completed scheduler service.
