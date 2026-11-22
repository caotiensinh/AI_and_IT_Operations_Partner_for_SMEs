# Staging dispatch credential and role separation

A separate `sme_dispatch_runtime` Postgres password login can assume only
`sme_dispatch`; it cannot assume web/auth/ingest roles or perform raw DML
against the alert outbox. CI authenticates with the generated ephemeral
password and validates authorization failures.

No dispatcher network client runs, and no customer destination is configured.
Production requires a secret manager, tenant-specific destinations, idempotent
provider integration and auditable notification policy.
