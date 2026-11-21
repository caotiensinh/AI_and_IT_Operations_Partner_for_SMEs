# Asahi integration checkpoint — 2026-11-21

## Verified and persisted
- PR #28: tenant/site-scoped Asahi sample storage, runtime SELECT-only RLS,
  session/RBAC metrics endpoint, responsive desktop/tablet/mobile Monitoring
  view, two-tenant Chromium E2E, six CI workflows PASS.
- PR #29: trusted HTTPS GET status adapter using a configured CA trust root,
  Bearer token, no redirect/proxy, and bounded timeout/body size; five CI
  workflows PASS.
- PR #30: session-authenticated tenant audit of telemetry reads; PostgreSQL
  negative tests, five CI workflows PASS.
- All three merged to `main` after verifying PR heads and mergeability.

## Not accepted
- No live agent registered, no actual sampled hardware data.
- No scheduler, signed device enrollment, secret rotation, agent heartbeat,
  storage retention, production TLS/login, alerting or time-series aggregation.
- Current Asahi HTTPS poller is not wired into the database write path and has
  not contacted any customer's device.
- CI's synthetic sample data is for isolation/UX verification only.

## Next independent acceptance target
M2.5: trusted device enrollment + isolated agent collection worker.
Required proofs: no URL/credential from browser input; tenant-binding is resolved
only by server enrollment; pinned HTTPS identity checked; replay and duplicate
sample rejection; restrictive DB credential; real agent A/B benchmark.
