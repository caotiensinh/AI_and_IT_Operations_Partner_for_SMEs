# Dispatch and worker service checkpoint — 2026-11-22

## Persisted and verified
- PR #47: tenant-scoped alert queue lease/ack/retry/dead-letter SQL contract,
  restricted `sme_dispatch` NOLOGIN role, two-dispatcher race and role denial
  verified in disposable PostgreSQL. 250/250 tests and 5 workflow PASS.
- PR #49: fail-closed interruptible worker lifecycle primitive with bounded
  retries/failures and sanitized status snapshots. 258/258 tests and 5
  workflow PASS.
- PR #50: separate password-authenticated staging login for dispatcher with
  denied app/auth/ingest role escalation and raw outbox reads/writes.
  Staging Compose smoke PASS on both push and PR before merge.

## Not accepted
- No real delivery provider, tenant destination policy or secrets store.
- Outbox uses at-least-once semantics; a provider may receive duplicates
  after ACK loss unless it supports an event-id idempotency key.
- No long-running daemon is deployed, no real-agent enrollment, no physical
  metric evidence, no production TLS/OIDC handoff, no customer notifications.
- Dispatcher role authorizes queue mechanics but is not suitable as a
  customer-facing multi-tenant API principal.

## Next acceptance gates
1. Implement tenant-managed destination policy and secrets outside Git/env.
2. Implement notification provider adapter with delivery-idempotency proof.
3. Hook worker to supervised runtime with health endpoint and operator-owned
   device credentials, verify restart and network partition.
4. Execute physical Asahi agent A/B telemetry test in an isolated LAN.
