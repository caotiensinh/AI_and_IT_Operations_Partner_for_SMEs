# Spec 006 — Credential-bound Asahi ingest

## Goal
Persist a normalized, recent Asahi sample only if the server recognizes an
active enrollment whose tenant/site/device comes from privileged PostgreSQL data.

## Threat boundaries
- Enrollment and credential rotation are **privileged offline operator actions**.
  No browser, public endpoint or ordinary SME user may write enrollments.
- A separate NOLOGIN `sme_ingest` role may execute exactly one verified-sample
  SQL function; it cannot SELECT enrollment secret hashes or directly INSERT.
- Function derives tenant/site/device entirely from enrollment and verifies
  credential hash, active enrollment and active tenant; no tenant IDs in request.
- Reject stale/future observations, duplicate timestamps, bad percentages,
  wrong credentials and revoked enrollments. Writes are auditably scoped but
  a full independent ingest audit stream remains future work.
- Existing HTTPS poller verifies TLS from an operator-provisioned CA.

## Acceptance
PostgreSQL 16 integration test proves accepted sample, duplicates rejected,
cross-tenant credential mismatch rejected, revoked enrollment rejected,
wrong-site enrollment FK rejected, direct writes and enrollment reads denied
to `sme_ingest`, application role unable to call ingest function.
CI exercises read path and Chromium regression.

## Non-goals
No real agent connection, no issuance/rotation UI, no secret-manager integration,
no scheduler, no multi-node credential inventory, no alerts, no HA.
This is not production-ready device onboarding.
