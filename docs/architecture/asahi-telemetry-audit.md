# M2.4 — Audited Asahi telemetry read

The protected Monitoring endpoint now calls the same tenant-session-backed audit
function as asset listing, with a new closed vocabulary entry:
`action=telemetry.read`, `target_type=telemetry`.

- Successful reads, including empty authorized responses, append a row before
  committing the same transaction.
- A denied cross-tenant request cannot write an audit event as another tenant.
- The audit function does not accept arbitrary action/target pairs.
- Tests exercise real PostgreSQL 16 with valid/denied requests.
- Audit is not externally immutable: production tamper-evident shipping and
  retention policy remain release gates.

This does NOT imply that a live agent is connected or that telemetry writes are
allowed from the API.
