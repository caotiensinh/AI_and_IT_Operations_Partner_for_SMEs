# Asahi durable operations checkpoint — 2026-11-22

## Persisted, validated and merged
- **PR #41, M2.10**: PostgreSQL durable alert state and transactional
  deduplicated outbox, protected by enrollment credential and role boundaries.
  216/216 Python/PostgreSQL tests PASS, five workflows PASS.
- **PR #42, M2.11**: accepted sample and alert evaluation now share the same
  transaction. Failure to evaluate rolls back the sample; duplicate timestamp
  does not reevaluate. 218/218 tests and five workflows PASS.
- **PR #44, M2.12**: PostgreSQL conditional lease acquisition and completion
  per enrolled device, bounded lease time, persisted next_due, concurrent
  claimer test and role-denial tests. 229/229 tests and five workflows PASS.
- **PR #45, M2.13**: synchronous single leased worker tick integrates
  claim→ingest→complete, with tested retry and no false success.
  238/238 tests and five PR workflows PASS.

## Security and correctness evidence
- Cross-tenant alert state, duplicate/old timestamps and forced credential
  mismatch are covered by SQL integration tests.
- Concurrent evaluation uses locked per-device/metric state rows and unique
  outbox keys. Two poll claimants compete atomically in PostgreSQL.
- Both the ingest authorization and lease acquisition derive tenant and
  device identity from privileged enrollment records.
- Web and ingest roles are denied direct writes to protected state/outbox.
- The stack continues to pass Chromium and staging regression checks.

## Not accepted
- No real Asahi agent has been contacted, registered or measured.
- No always-on worker service or distributed task loop is running.
- No outbox dispatch, email/SMS, operator acknowledgement, retention or
  incident management exists.
- No credential rotation/secret manager or production OIDC/TLS cutover.
- Crash recovery is bounded by a lease timeout, but longer tasks still need
  lease renewal and process-level observability.
- These are **disposable CI tests and code increments**, not customer production.

## Next acceptance gates
1. Implement durable outbox delivery/ack with tenant-specific channel policy.
2. Add safe worker executable/service with limited concurrency and structured
   logs, secrets sourced from a secret manager.
3. Verify an approved physical Ubuntu Asahi agent via TLS, then test a
   separate Windows data source; never open a public ingest endpoint.
