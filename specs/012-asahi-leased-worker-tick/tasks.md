# Spec 012 — Leased worker single tick

## Scope
Implement one synchronous acquisition→poll→ingest→completion cycle using
existing trusted enrollment and PostgreSQL lease functions.

## Accepted
- [x] Worker refuses invalid UUID, never polls without a lease.
- [x] Successful ingest completes the lease and persists next_due.
- [x] Duplicate telemetry is not falsely reported as a new insert.
- [x] Poll errors schedule a retry interval and propagate the error.
- [x] Failed lease completion is not reported as success.
- [x] Real PostgreSQL tests verify ingest once, cooldown and retry.
- [x] 238/238 Python/PostgreSQL tests PASS; five PR #45 CI workflows PASS.
- [x] PR #45 merged into main.

## Open
- [ ] Add a long-running service loop, backpressure and cancellation.
- [ ] Add lease renewal for long-running poll operations.
- [ ] Integrate a real agent with approved TLS and operator-held secrets.
- [ ] Test restart, power loss and network partitions with physical hardware.
