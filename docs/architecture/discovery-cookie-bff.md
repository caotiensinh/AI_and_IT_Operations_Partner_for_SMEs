# Spec 003 — Cookie BFF and tenant selector (slice 031)

## Objective and architectural decision
Use the existing OIDC Authorization Code + PKCE/state/nonce and first-party opaque session, but keep the session credential in a Secure/HttpOnly host-only cookie. Frontend code must never receive a bearer token in normal use. Keep the legacy bearer-only API available separately for synthetic E2E/compatibility; a cookie-mode deployment must expose **only** the BFF behind its approved HTTPS origin.

## Backend contract
- `GET /auth/oidc/start` and `GET /auth/oidc/callback` are composed into the BFF only when an operator supplies a trusted `OIDCLoginFlow`. No provider/issuer/token endpoint/JWKS or callback URL is accepted from the browser.
- `GET /auth/session/tenants` verifies the `__Host-sme_session` cookie against active session, membership and tenant status. Returns a list of `{id,label}` and a session-bound CSRF token, never the session secret.
- `POST /auth/session/logout` requires the same-origin `Origin` and matching `X-CSRF-Token`, revokes the server-side session and deletes its cookie.
- Existing `/v1/tenants/{id}/...` API routes are wrapped by an ASGI middleware that rejects user-provided `Authorization`, checks a valid cookie and injects a bearer header **only into the internal server request**, preserving existing PostgreSQL session+tenant RBAC and idempotency enforcement.
- Unsafe methods reject missing or wrong `Origin` and `X-CSRF-Token` before invoking any API; signed CSRF is HMAC-SHA256 keyed by an operator-provided unpredictable 32+ byte server secret and bound to the opaque session. Only exactly the configured `https://host[:port]` origin is accepted.
- Every protected response is no-store; no CORS exceptions or credential-bearing query parameters are added. Session cookies must be set with `__Host-`, Secure, HttpOnly, SameSite=Lax and Path=/ by the OIDC callback. The BFF requires HTTPS configuration.
- `sme.list_session_tenants(digest)`, migration 0012, is a narrow SECURITY DEFINER operation. `sme_app` receives EXECUTE only; it does not gain raw session, identity or membership-table access. At most 100 tenant choices are returned, above which the endpoint fails closed.

## Frontend contract
Normal Vite builds **default to cookie mode** (`VITE_DISCOVERY_AUTH_MODE` unset or anything except `pilot`). On load the frontend requests `/auth/session/tenants` with same-origin credentials. When signed out, a link starts OIDC. When signed in, it shows the authorized tenant names; choosing one invokes the unchanged Discovery endpoints using cookies and a CSRF header on mutation, without reading/saving bearer credentials. Cookie logout calls the backend.

The legacy manual Tenant UUID/token form exists only with the **explicit** `VITE_DISCOVERY_AUTH_MODE=pilot` build setting, intended for disposable CI and developers. The existing Playwright synthetic browser suite forces this pilot mode and must remain PASS. Never deploy a pilot-mode bundle to customers.

## Security gate and limitations
PostgreSQL tests require tenant listing, active/disabled membership checks, cookie-only read, cross-tenant refusal, CSRF absent/wrong-origin/wrong-token denials, authorized idempotent create, server-side logout/revocation, and OIDC callback composition. Unit tests require client sends CSRF on writes and no bearer header in cookie mode. Full E2E with a live trusted identity provider and TLS/browser cookie issuance is **not** yet proven; the current Playwright suite exercises the explicit synthetic pilot mode, not production login.

**Not production-ready:** No provisioned IdP credentials or trusted JWKS rotation, no deployment composition of reverse proxy + app-role DB access, no external OIDC end-to-end, no rate limiting, no CSRF token rotation after privilege changes, no formal customer onboarding/consent, no tenant quota enforcement and no penetration/security audit. Do not use customer data.

## Local reproducibility
- Run PostgreSQL 16 with disposable `sme_test`, migrations through 0012; never connect this test setup to a customer database.
- Frontend: `cd web/discovery && npm install && npm test && npm run build`.
- Synthetic legacy E2E automatically sets `VITE_DISCOVERY_AUTH_MODE=pilot` through the Playwright webServer environment.
- A trusted server operator must instantiate `create_cookie_discovery_app(connect,csrf_secret=<32+ random bytes>,trusted_origin="https://workspace.example",oidc_flow=<pinned verified flow>)`, reverse-proxied with TLS on the **same origin** as the static app. There is deliberately no hardcoded login provider or development bypass.
