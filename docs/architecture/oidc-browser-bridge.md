# Spec 003 — OIDC Browser Bridge (slice 030)

## Goal
Deliver the first browser-facing adapter for the **existing**, independently tested PostgreSQL-backed OIDC Authorization Code + PKCE/state/nonce flow, without leaking a first-party session token into JavaScript, redirect URLs, browser storage, or logs.

## Endpoints
- `GET /auth/oidc/start` creates a fresh one-use state, PKCE verifier, nonce and random browser binding through `OIDCLoginFlow.start()`. It redirects to the **configured** external IdP authorization endpoint. The binding is stored in a `__Host-sme_oidc_binding` Secure/HttpOnly/SameSite=Lax/Path=/ cookie, with 5-minute age.
- `GET /auth/oidc/callback?state=...&code=...` checks the browser-binding cookie and single-use state, then calls `OIDCLoginFlow.complete()`. The latter performs pinned token exchange, RS256/JWKS/issuer/audience/nonce verification and mints a short-lived first-party session only for an active internal identity/membership via `sme_auth`. On success it sets a `__Host-sme_session` Secure/HttpOnly/SameSite=Lax/Path=/ cookie and redirects with **303** to a validated, fixed relative application path. No session token appears in response body, query parameters or URL fragment. On error it returns a generic 401 and clears the temporary binding cookie.
- Response headers always include `Cache-Control: no-store`.

## Security decisions
- Never accept `redirect_uri`, `token_endpoint`, `issuer`, `client_id`, `jwks` or `post_login_path` from the incoming browser request.
- The provider authorization/token endpoints and expected public JWKS must be provisioned through trusted HTTPS server configuration and verified against operator-approved IdP metadata. The current `PostgresLoginStore` is responsible for single-use replay protection.
- There is **no insecure mock login route**, no cross-origin CORS grant, no session credentials in localStorage, no login-by-username/password fallback and no automatic new membership/tenant creation.
- `__Host-` cookies require a trusted HTTPS browser origin. This adapter must not be enabled on a public host until a correct reverse proxy/TLS deployment is in place.
- The session cookie is **not yet consumed by the current Discovery API**. The React pilot still accepts manually supplied test bearer credentials. Shipping an HttpOnly cookie alone does not implement CSRF-safe backend authorization: a separate BFF session gateway with POST CSRF enforcement and server-side tenant selection is mandatory.

## Acceptance and test evidence
- Unit/HTTP tests verify secure cookie flags, no-store headers, pinned post-login redirect, callback failure handling, missing/wrong binding rejection, stale/replayed state rejection and no credential leakage.
- Existing identity tests verify signature, nonce, PKCE, inactive membership and restricted `sme_auth` database privileges.
- Browser end-to-end tests for an actual configured IdP and a CSRF-protected tenant-scoped gateway remain future acceptance gates.

## Dependencies
Stacked after PR #36, before the planned BFF/tenant-selector login integration. No merge, release, customer data, or production deployment is authorized by this slice.
