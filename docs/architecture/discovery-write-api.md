# Spec 003 — guarded creation of research cases (pilot)

## Scope
Migration 0006 (followed by 0007 for idempotency) introduces a separate NOLOGIN/NOBYPASSRLS `sme_discovery_service` role and append-only case creation events. The runtime `sme_app` role retains SELECT-only privileges on discovery records and cannot read audit events. Case creation occurs only through `sme.create_discovery_case` (SECURITY DEFINER owned by the dedicated role).

`POST /v1/tenants/{tenant_id}/research-cases` accepts JSON `{site_id, label, company_code}` and returns 201 with a newly generated UUID and `research` status. The API validates the bearer format. The database function independently verifies the live session digest and active membership; after verification it assigns transaction-local tenant context, verifies site ownership, then permits only tenant-scoped owner/admin/manager or site-scoped manager. Operators/viewers, suspended tenants and other-tenant sessions are denied. Case INSERT and audit INSERT share a single transaction; if the audit write fails the case must roll back.

## Boundaries
- NOT a general-purpose write role; there is no direct runtime INSERT, UPDATE or DELETE grant.
- No requirements, source document, attachments or customer records may be created by this endpoint.
- This write capability is for synthetic/test tenants only until browser login/CSRF, rate-limiting, consent, schema migration controls, monitoring and deployment trust boundaries are verified.
- Audit events capture action, actor ID, tenant, case and time, not private payloads. They are protected from runtime SELECT, but immutability against privileged DB owners and retention/exports need separate hardening.
- **Superseded by migration 0007:** case creation requires an `Idempotency-Key` and uses an actor/tenant-scoped atomic reservation. Retry and concurrency details are in [discovery-idempotency.md](discovery-idempotency.md). Retention/expiry of keys is still unimplemented.
- CSRF/browser secure cookies are not implemented; bearer sessions are only a pilot capability.

## Validation gates
Automated PostgreSQL 16 tests must demonstrate manager site success, persisted audit, viewer denial, cross-tenant and invalid-site denial, malformed input rejection and direct-table privilege denial. A passing synthetic test is not customer deployment authorization.
