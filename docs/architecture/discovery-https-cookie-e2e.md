# Spec 003 — HTTPS Cookie BFF Chromium Acceptance (slice 032)

## Scope and acceptance
This is an automated **real browser / real database** verification of the already-implemented session-cookie Discovery Workspace, not an actual identity provider deployment. The test runner provisions a disposable PostgreSQL 16 database with migrations 0001–0012, a synthetic manager identity/session and random cookie credential, and exposes an HTTP FastAPI BFF only on loopback behind a temporary **HTTPS** Vite reverse proxy on `https://127.0.0.1:5174`. A newly generated short-lived, self-signed localhost TLS certificate is used exclusively inside CI, with Playwright configured to trust it for the test.

The Playwright test harness injects the previously provisioned synthetic `__Host-sme_session` cookie into a browser context. **This bypasses an external IdP solely to test the cookie BFF**; no application endpoint exists for direct cookie issuance or fake customer login.

### Positive browser proof
1. Without cookie, workspace displays the Japanese OIDC login action.
2. With synthetic secure HttpOnly cookie, browser loads the server-authorized tenant list **without typing tenant UUID or a bearer credential**.
3. Selecting a tenant lists site-authorized discovery cases, creates a case, records metadata-only evidence, creates a source-linked explicit requirement, confirms it with a rationale, and reads reviewer history—all through the cookie BFF, PostgreSQL and CSRF-bound write requests.
4. JavaScript cannot read the session cookie; localStorage and sessionStorage contain no session secrets.
5. Logout revokes the database-backed session, clears the cookie and makes the tenant session endpoint return 401.

### Negative browser proof
1. No Origin and no CSRF header → 403 on a write.
2. Forged external Origin with a correct CSRF header → 403.
3. User-supplied Authorization bearer alongside session cookie → 400.
4. After attempted forged writes, the attempted unauthorised case is absent from the case listing.

### CI
Run `Discovery HTTPS Cookie E2E` workflow. On the final implementation SHA, both browser tests must pass; existing bearer-pilot Playwright test and TypeScript/Vite frontend tests must still pass. All browser evidence is synthetic. Certificate key and session fixture are transient and excluded from uploads.

## Threat boundaries and non-goals
- **Not a real OIDC browser login:** no IdP authorization redirect, signed ID token, discovery/JWKS, provider callback, or account provisioning are exercised in this slice.
- **Not production TLS:** the certificate is self-signed, short-lived and browser trust is bypassed only in CI; production requires a trusted certificate and proxy verification.
- **Not deployment:** no external hosts, internet-facing listeners, production secrets, production PostgreSQL or real customer content.
- **Not a security certification:** complete threat-model sign-off, CSRF replay analysis, cookie rotation, CSP/HSTS, signed host/forwarded-header validation, rate limits, audit monitoring, disaster recovery, and independent penetration test remain to be done.
- **No UI credential leakage claims beyond these explicitly tested session/cookie surfaces.**

## Reproduction
The GitHub Actions workflow is canonical. Manual reproduction requires localhost-only disposable `sme_test`, test token fixture, Python 3.12, Node 22, Chromium, and `openssl`. Run the scripted seed only with `SME_E2E_ONLY=1` and `SME_E2E_COOKIE_MODE=1`; the BFF refuses any non-local database. `DISCOVERY_TLS_CERT` and `DISCOVERY_TLS_KEY` must point to freshly generated test-only files; `DISCOVERY_API_ORIGIN` must be a loopback URL. The Chromium suite is `npx playwright test --config=playwright.cookie.config.ts`.

Do not publish this disposable server. Merge only in dependency order after reviews.
