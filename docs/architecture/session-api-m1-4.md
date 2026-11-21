# M1.4 — Protected API and tenant session boundary

## Delivered scope
- `sme.sessions` holds SHA-256 digests of 32-byte entropy opaque bearer tokens. No plaintext session token persisted.
- `sme.resolve_session(digest,tenant)` is a narrow SECURITY DEFINER function validating active session, active tenant and active membership.
- `sme.revoke_session(digest)` allows session owner via bearer possession to revoke; no app-role direct read/write of session table.
- `GET /v1/tenants/{tenant_id}/assets` uses a single transaction: runtime DB role, session validation, transaction-local tenant context, role assignments and resource-scoped RBAC.
- `POST /v1/session/logout` invalidates the opaque session.
- E2E tests operate on disposable PostgreSQL 16 and FastAPI TestClient for cross-tenant, invalid/expired/revoked session, disabled memberships, suspended tenant, role revocation and logout.

## High-priority constraints before real deployment
- **No OIDC authorization code callback, PKCE/state/nonce or production session issuance yet.** Session fixtures are created by privileged tests only. A future callback must verify OIDC, match issuer/subject in DB, then mint high-entropy random session token and store digest through a dedicated restricted auth role.
- The API uses an explicit bearer header for the pilot; browser production should use HttpOnly Secure SameSite cookies with CSRF protection and session rotation, not persist bearer tokens in localStorage.
- `sme_app` is an abstract NOLOGIN role for tests. Real deployment requires dedicated least-privilege LOGIN role and non-superuser connections. CI switches role from PostgreSQL superuser only for test convenience.
- Current asset model has no department_id. Department-level access to assets is intentionally excluded until asset ownership schema and recursive department query are implemented.
- Database application user can set `sme.tenant_id` within transactions; it must be controlled by trusted backend code, not leaked to operators or edge devices.
- Trusted JWKS discovery/rotation, multi-region HA, immutable audit, rate limiting, security headers, monitoring, pooled-connection concurrency tests and penetration review remain open.
- Security definer functions must be code-reviewed, use pinned search_path and minimal execute privileges; privileged migrator must not be exposed to application runtime.
- Implement security audit and SLO/backup/restore before customer data is admitted.

## Verification
`python -m unittest discover -s tests -v` on CI with SME_TEST_DATABASE_DSN, FastAPI, psycopg and httpx.
