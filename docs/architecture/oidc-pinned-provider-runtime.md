# Spec 003 — Pinned enterprise OIDC provider adapter and runtime (slice 034)

## Problem solved
The prior OIDC browser E2E used an isolated synthetic IdP and hardcoded CI token exchange, not an operator-provisioned enterprise identity provider. This slice adds a **provider-neutral HTTPS OIDC client** and **operator-only runtime factory**. It reuses the existing code + PKCE/state/nonce/PostgreSQL `sme_auth` flow instead of inventing authentication or accepting identity claims from JavaScript.

## L1/L2/L3 integration
- **L1 Browser:** Japanese Workspace → `/auth/oidc/start` → external IdP → `/auth/oidc/callback`, `__Host-sme_session` and `/auth/session/tenants`. No manual tenant UUID, no JavaScript session token in cookie mode.
- **L2 Auth / BFF:** `PinnedProvider` validates fixed operator-approved HTTPS issuer, authorization/token/JWKS URLs, confidential client registration, callback and MFA policy; `VerifiedProviderClient` checks operator-pinned OIDC discovery metadata and trusted JWKS, rejects redirects/oversized responses and exchanges authorization code with PKCE and HTTP Basic client authentication. `OIDCLoginFlow` performs signature, issuer, audience, nonce and membership checks, with throttled provider-pinned JWKS refresh **only on an unknown signing key ID**.
- **L3 Trust and Data:** `PostgresLoginStore` uses the separately provisioned `sme_auth` DB login; `create_cookie_discovery_app` uses the separate application DB login and existing `sme_app` RBAC/CSRF barriers. No raw session table grants to app/browser roles.

## Configuration contract
The factory `sme_partner.discovery_runtime.create_configured_discovery_app()` requires **all** of:

| Environment variable | Operator value / origin |
|---|---|
| `SME_APP_DATABASE_DSN` | Secret Manager: app-only DB login, allowed to use `sme_app` |
| `SME_AUTH_DATABASE_DSN` | Secret Manager: **different** auth-only DB login, privileges for `sme_auth` functions |
| `SME_TRUSTED_ORIGIN` | Exact public HTTPS origin of the BFF and React application |
| `SME_CSRF_SECRET_HEX` | Independent unpredictable secret, at least 32 bytes encoded as hex |
| `SME_OIDC_ISSUER` | Exact operator-approved HTTPS OIDC issuer including provider tenant path if applicable |
| `SME_OIDC_AUTHORIZATION_ENDPOINT` | Exact approved HTTPS authorization URL |
| `SME_OIDC_TOKEN_ENDPOINT` | Exact approved HTTPS token URL; may be on a different approved host |
| `SME_OIDC_JWKS_URI` | Exact approved HTTPS JWKS URL; may be on a different approved host |
| `SME_OIDC_CLIENT_ID` | Registered confidential application client ID |
| `SME_OIDC_REDIRECT_URI` | Exactly registered HTTPS `/auth/oidc/` callback |
| `SME_OIDC_CLIENT_SECRET` | Secret Manager: confidential application client secret, never checked into Git |

Optional: `SME_OIDC_REQUIRE_MFA=true|false` (default **true**), `SME_OIDC_ACCEPTED_ACR` (comma-separated **provider-vetted** assurance values). Do not interpret user-supplied `amr`/`acr` claims as roles or memberships. The operator must ensure provider settings and MFA evidence conform to local policy; a default synthetic IdP without MFA is **not** an eligible production provider.

### Bootstrap
1. Register a confidential server-side OIDC web application at the chosen enterprise IdP (not in this repository). Configure exact HTTPS callback URI, client authentication, requested scopes and assurance policy.
2. Confirm issuer, authorization endpoint, token endpoint and JWKS URL directly with trusted provider documentation/admin discovery. Record/pin these in the deploy secret manager/config; **never automatically trust alternative URLs in token headers or discovery responses**.
3. Provision **two different** least-privilege PostgreSQL login credentials, validate they can call only their expected roles/functions, and configure the same-origin HTTPS reverse proxy and static frontend.
4. Inject the environment values through Secret Manager and construct the ASGI application via `create_configured_discovery_app()`. Provider discovery and JWKS are checked at startup; the app will refuse startup when metadata or key material disagrees with pinned operator configuration or the provider is unavailable.
5. Run an authorized canary login with a preprovisioned identity/membership; verify correct tenant scoping, MFA policy, failed callback/replay behavior, logout, token redaction and operational alerting before any pilot.

## Rotation, rejection and operational policy
- Provider discovery cannot change endpoint targets at runtime. HTTP redirects are rejected; normal CA TLS validation is required.
- JWKS refresh happens only for an **unknown signing key ID** from an otherwise well-shaped token, never from `jku`, `x5u` or user-supplied URLs; refresh is throttled to once per 60 seconds per flow instance. Refresh uses the **fixed operator-pinned JWKS URL** and still requires successful signed JWT verification.
- Do not delete old signing keys from the provider during rollover until in-flight login transactions expire. New malformed/duplicate/non-RSA keys fail closed.
- Network timeout is 5 s by default; all JSON payloads and ID token sizes are capped. Provider failures do not issue sessions, and server responses must never include provider secrets or token bodies.
- Rollout/rollback means restoring pinned configuration and last validated runtime version, **not** disabling JWT verification or skipping MFA.

## Test evidence and explicit limits
Offline test doubles verify pinned multi-host endpoints (including environments where issuer/token/JWKS are on different HTTPS hosts), metadata mismatch, secret-bound token exchange, redirect denial, payload bounds, signature-key rotation and cooldown, invalid config and startup fail-closed. Existing PostgreSQL and Chromium synthetic-IdP E2E workflows remain regression gates.

**Not yet production-ready:** no real Microsoft Entra ID, Google Workspace or other enterprise tenant has been registered/connected; no real application client secret, live JWKS rollover or enterprise user authenticated in this session; no trusted internet-facing deployment, independent security audit, certificate rotation, rate limiting or customer consent. Integration with a selected provider requires actual operator authorization and secrets, followed by its own end-to-end acceptance; a green synthetic CI run cannot substitute for it.

All tests use synthetic data. PRs remain stacked and unmerged until dependency/security review.
