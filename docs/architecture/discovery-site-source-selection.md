# Spec 003 — RBAC-scoped Site and Source Selectors (slice 029)

## Goal

Remove brittle UUID hand-entry from the Japanese Business Discovery Workspace while keeping authorization authoritative on the server. No external documents or actual customer data are imported.

## Implemented endpoints

`GET /v1/tenants/{tenant_id}/discovery-sites?limit=50&after={uuid}`

Returns a keyset page of only the sites where the authenticated identity **may create a discovery case**. Tenant-scoped owner/admin/manager may select tenant sites; site-scoped manager may select only assigned sites. A viewer/operator receives an empty list, even if able to read some cases. Site filtering is applied **in PostgreSQL before LIMIT** so hidden sites never displace authorized rows. All returned site IDs are accompanied by their display label. The endpoint is not a generic site directory and grants no new write permissions.

`GET /v1/tenants/{tenant_id}/research-cases/{case_id}/sources?limit=50&after={uuid}`

Returns the actual persisted metadata `[{id,document_label,page}]` from PostgreSQL. Session and membership are checked; the case must belong to the tenant and the requesting role must have READ scope for its site. Hidden and missing cases both return 404 (assuming valid tenant session). The endpoint does not return PDF bytes, document content, or private review rationale.

Both routes accept `limit=1..100` and a UUID `after`; use `next_cursor` until null. No global counts or snapshot isolation are promised.

## UI

- Case creation uses a dropdown of server-authorized sites instead of requiring a Site UUID.
- Source selection uses a dropdown of registered sources instead of a source UUID text field.
- Source list is fetched when selecting an existing case, and can be reloaded after disconnect/reconnect.
- If a site or source list exceeds one page, `さらに読み込む` loads the next cursor.
- A viewer cannot gain site creation rights by manipulating frontend fields; PostgreSQL re-checks the permission on POST.
- Opaque test bearer login remains developer-only. A real OIDC/PKCE login, tenancy chooser and CSRF-safe deployment are *not* implemented.

## Mandatory acceptance evidence

1. PostgreSQL tests: viewer has no writable site choices, site-scoped manager sees only assigned site, tenant manager paginates sites, site-limited source reader cannot access hidden case and cross-tenant context cannot see metadata.
2. Real Chromium + FastAPI + PostgreSQL test: choose a labeled site, create a case and source, disconnect/reconnect, see persisted source, create an explicit requirement from selected source, submit review and read decision history.
3. TypeScript/Vite production build and unit tests PASS on the final code SHA, not only an earlier intermediate commit.

## Boundaries

This is a research pilot using disposable, synthetic data. No production credentials, confidential customer files or personal data may be supplied. No contract approval, true customer onboarding, document storage, customer consent, enterprise OIDC, browser session hardening, backups or live deployment are claimed.
