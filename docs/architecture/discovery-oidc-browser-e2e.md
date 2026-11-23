# Spec 003 — Full OIDC Authorization Code / PKCE Browser E2E (slice 033)

## Goal
Prove that the Japanese Business Discovery Workspace can perform a **complete browser round-trip** using Authorization Code + PKCE S256, DB-backed one-time state and a genuinely **RS256-signed** ID token, through the existing OIDC callback, without exposing opaque first-party credentials to JavaScript. The test is limited to an isolated, local synthetic identity provider.

## CI topology
```
Chromium → https://127.0.0.1:5174 (ephemeral Vite TLS)
                 ├─ /auth/oidc/* → 127.0.0.1:8001 (FastAPI cookie BFF)
                 ├─ /oidc-test/* → 127.0.0.1:8002 (local synthetic IdP)
                 └─ /v1/*, /auth/session/* → FastAPI BFF
FastAPI BFF → PostgreSQL 16 sme_test
FastAPI OIDC flow → sme_auth role / one-use state → token exchange (localhost only)
Synthetic IdP → one-use auth code, PKCE verifier check, RS256 ID token
BFF → pinned, ephemeral JWKS → signature/issuer/audience/nonce → active identity
       → fresh HttpOnly/Secure session cookie → authorized tenant selector
```

The IdP is not a company login provider. The authorization endpoint, expected issuer, client ID and redirect URI are pinned to synthetic, known test values by CI. RSA keypair and JWKS are generated once in the GitHub Actions job and deleted afterward; the private key remains a mode-0600 local file, never stored in Git. The BFF does not fetch token-provided URLs. A test HTTPS certificate is self-signed and accepted only by the Playwright test browser.

## Positive acceptance
1. Starting unauthenticated displays the OIDC login link, not manual bearer or tenant UUID entry.
2. Browser follows /auth/oidc/start and /oidc-test/authorize, carrying random one-time state, nonce, and S256 challenge.
3. Synthetic IdP issues a random one-time code, which BFF exchanges server-side using the matching original PKCE verifier; the IdP rejects mismatched PKCE and code replay.
4. BFF verifies RS256 JWT with pinned, ephemeral JWKS and issuer, client ID and nonce, then `sme_auth` issues a first-party session only for the pre-provisioned identity and active tenant membership.
5. Browser receives a Secure/HttpOnly `__Host-sme_session` cookie, displays a tenant by its name, creates a case via the CSRF-gated BFF, and never sees the token in JavaScript-readable cookies/storage or the final redirect URL.
6. Logout invalidates the session, and a **new** full OIDC round-trip allows re-login and reading the persisted case.
7. Browser replay of a consumed callback state/code fails both before and after logout, without issuing a new session.

## Security and scope boundaries
- No username/password mock, external network IdP or synthetic login route is added to production. `/oidc-test` exists **only** on a separate disposable localhost test server; the BFF never hosts it.
- `PostgresLoginStore` uses `sme_auth` role for login transactions; the ordinary BFF app path uses `sme_app` and retains RBAC/tenant checks.
- Synthetic test records and keys are destroyed with the disposable CI environment; session values, authorization codes, state, nonce and private signing key are not printed.
- This is a valid protocol-flow E2E, **not** a real external provider interoperability test, trusted TLS deployment or independent security audit.
- Production gate remains open for actual IdP onboarding (issuer/client registration, trusted HTTPS, token endpoint authentication policy, JWKS rotation, consent, session rotation, threat model, rate limits, reverse-proxy hardening, audit and penetration testing).

## Verification
- GitHub Actions: `Discovery OIDC Authorization Code Browser E2E` must PASS on the final implementation SHA.
- Regression workflows must preserve existing `Discovery HTTPS Cookie E2E`, `Discovery Real Browser E2E`, and `Discovery Workspace UI` green checks.
- The suite executes against a disposable PostgreSQL 16 service and migrations 0001–0012 including auth migration 0004, without production/real customer data.
