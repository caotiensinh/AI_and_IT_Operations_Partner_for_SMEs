# M2.5–M2.6 acceptance checkpoint

## Verified
- PR #32: enrollment-bound trusted database write, isolated `sme_ingest`
  execution role, duplicate timestamp rejection, token mismatch rejection,
  revoked/suspended tenant rejection and cross-tenant/site constraints.
- 184/184 Python/PostgreSQL tests PASS on PR #32. Five related workflows PASS.
- PR #34: integration of trusted HTTPS poller, worker and PostgreSQL storage
  with an HTTP-mocked upstream agent; 187/187 Python/PostgreSQL tests PASS.
- Both PRs merged to main; exact merges verified on GitHub.

## Not yet verified
- Live physical Asahi agent, certified enrollment TLS endpoint, token rotation.
- Production credential separation and independent login for `sme_ingest`.
- Production scheduler, failure retry/DLQ, long-term metrics storage,
  backpressure, real-device telemetry across two customer LANs.
- No agent endpoint or credential from browser is accepted.
- The user-facing UI still receives only the most recent accessible sample.
- The current CI synthetic agent response is NOT a physical hardware test.

## Next acceptance
Run a LAN-only pilot with one real Ubuntu server agent and a separate
Windows target or agent, using out-of-band CA/credentials and independent
operators. Validate correct tenant scope and failure isolation.
