# Technical Plan — Three-Layer Enterprise Platform

## Architecture decision
Modular monolith for Python API and business workflows, backed by separate Rust edge/ingest worker and Python AI workers. Contracts over OpenAPI and versioned events. Shared SaaS is not a single global unrestricted data namespace.

## Data flow
Browser/PWA → reverse proxy (TLS/security headers) → Python API (OIDC session/authz) → domain service → tenant-scoped repository → PostgreSQL RLS.
Background: domain service → transactional outbox → queue → Python/Rust worker → tenant-scoped storage → outcome event → audit + notification.
Edge: device certificate → broker/ingest endpoint → tenant/site/device authorization → buffered measurements or media object store.
AI: tenant policy → approved processor → reviewed result → auditable business action; never auto-execute irreversible changes based solely on an LLM output.

## Implementation sequence (dependency-aware)
P0 foundation: contracts, migrations, tenant identities, tenant-scoped RLS, automated security tests.
P1 workspace: OIDC, membership switch, roles/scope, audit, responsive shell.
P2 first commercial pilots: OA-01 OCR/approval and IT-01 infrastructure monitoring.
P3 modules: visual inspection and IoT device management when pilot demand is proven.
P4 scale: dedicated deployments, backup/restore, interoperability and SLO improvements.

## Service boundaries
- identity/tenant: onboarding, memberships, org tree, roles, entitlements, support grants.
- workspace: inbox, dashboard preferences, notifications.
- office: source documents, extraction, review and export adapters.
- itops: asset inventory, checks, alerts and incidents.
- vision: camera definitions, inference results and human review.
- iot: site, device, measurements and alert rules.
- platform: jobs, audit, objects, observability and backup integration.

No module may query another module's table directly through arbitrary SQL: use explicit domain contracts.

## Verification plan
1. Python: pytest, type checks, formatting, migration tests, tenant security integration tests on real PostgreSQL.
2. Rust: cargo fmt, clippy, test, integration test for tenant/site-bound ingestion.
3. Frontend: typecheck, component/accessibility tests, Playwright cross-device task journeys.
4. Container and deployment: image scans, OIDC integration, secret scanning, backup and restore drill.
5. CI security gate: cross-tenant negative tests and forbidden support-data access must pass.
6. Evidence: retain CI run URLs, test outputs and release manifests per milestone.

## Delivery rule
Do not mark any implementation milestone PASS until a persisted change has been tested and reviewed. No claim of production readiness from a spec-only commit.
