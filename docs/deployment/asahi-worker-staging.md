# M2.7 — Isolated ingest credential and scheduler primitive

## Verified scope
- A dedicated staging `sme_ingest_runtime` LOGIN role may assume only
  `sme_ingest` (not `sme_app` or `sme_auth`).
- The application login `sme_runtime` remains separate.
- No direct enrollment SELECT or telemetry INSERT grants are added.
- The scheduler is a pure in-process component with monotonic interval,
  bounded retry deferral and attempt exhaustion, non-overlap and explicit outcomes.
- Staging CI checks DB role grants and forbidden direct database operations.
- Unit tests check run timing, transient failures, concurrency and invalid policy.

## Not implemented or accepted
- No persistent distributed scheduler, multi-process lease, durable queue,
  secret manager, rotation workflow, customer network connectivity or real
  Asahi hardware polling.
- No live worker container is enabled: this release does not read secret
  values from a runtime env file to poll an arbitrary endpoint.
- Retry deferral is in-process only, with no crash recovery. This component
  needs a durable attempt counter/dead-letter strategy for production.
- Device enrollment must remain privileged; never expose agent URL or token
  input through browser API.

## Required next acceptance
Demonstrate a local, verified TLS agent with an out-of-band approved
endpoint/certificate/credential and a non-root ingest worker; test that
revoking the enrollment immediately blocks writes, including after restart.
