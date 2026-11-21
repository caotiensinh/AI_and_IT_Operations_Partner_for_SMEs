# Spec 004 — Tenant-safe Asahi Monitoring read slice

## Goal
An SME operator with an active platform session sees **only** the latest
telemetry for devices assigned to sites they may access. Sensor values are
from persisted records, not synthetic frontend numbers.

## Scope
1. Reuse the existing Asahi telemetry normalization contract.
2. Model tenant/site/device sample ownership in PostgreSQL with a composite FK.
3. Preserve tenant FORCE RLS and prohibit application-role sample writes.
4. Serve only latest metric per device through existing membership and RBAC API.
5. Render a responsive Monitoring view on desktop/tablet/smartphone, including
   no-data and N/A sensor states.
6. Validate cross-tenant denial with PostgreSQL tests and real Chromium.

## Non-goals
Live agents, polling, ingestion, agent tokens, enrollment, alerts, GPU probing,
time-series graphs, fake live monitoring, workflow automation and production UI
authentication. The Asahi adapter is not activated.

## Acceptance criteria
- A session for Tenant A cannot query Tenant B telemetry (403).
- A tenant-scoped DB runtime SELECT excludes samples from other tenants.
- An app-role INSERT is rejected and wrong site binding fails a composite FK.
- Revoked/absent sessions cannot access metrics.
- Revoked or site-scoped RBAC excludes unauthorized devices.
- Latest of multiple samples per device is returned; NULL sensor stays N/A.
- Four Chromium viewport tests switch between two tenants and never display
  another tenant's hostname.
- Source-code tests, PostgreSQL 16, frontend build, staging Compose and Chromium
  checks all succeed before merge.

## Security boundary
Synthetic test seeding runs only with privileged disposable CI credentials.
The platform API never receives a telemetry ingest route or direct agent token.
