# Spec 007 — Asahi worker operations safety boundary

## Goal
Make ingest role separation real in staging, and add a bounded, testable
scheduler kernel without exposing a production agent integration prematurely.

## Acceptance
1. Unique generated ingest password is distinct from DB admin and web runtime.
2. `sme_ingest_runtime` assumes only `sme_ingest`; app and auth role membership denied.
3. DB role cannot read enrollment digests or insert samples directly.
4. Scheduling interval and retry are bounded, no concurrent duplicate work.
5. Authorization failures propagate, retries do not claim successful ingestion.
6. All GitHub Actions tests and staging Compose smoke PASS.

## Non-goals
Distributed scheduling, physical device access, secrets store, alert delivery,
production worker deployment. A real agent pilot requires enrollment authorization.
