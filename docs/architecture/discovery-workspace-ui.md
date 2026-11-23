# Business Discovery Workspace — UI slice 024

**Scope:** A real, Japanese-first React/TypeScript/Vite browser client for the already-tested discovery API. Not a production-ready login or customer-facing SaaS.

## User workflow
1. By default, the browser checks its first-party HttpOnly session through `/auth/session/tenants`. If unauthenticated, start OIDC via `/auth/oidc/start`. Choose a tenant **by displayed name from server-authorized memberships**; the BFF supplies a session-bound CSRF token for mutations. The synthetic/manual UUID + bearer form remains available **only** when `VITE_DISCOVERY_AUTH_MODE=pilot` is explicitly set for developer CI.
2. Read site/tenant-authorized case list. UUID cursor pagination follows backend `next_cursor`; search filters only currently loaded items, not a global backend search.
3. Create case by selecting an authorized site label (provided by the backend) and company archetype; use a stable `Idempotency-Key` until the logical create has returned. A failed request may be retried with the same key while form content stays unchanged.
4. Select case, read paginated requirements, see classification, approval state and source label/page.
5. Register metadata-only evidence source (label, page, client-generated UUID). Existing source metadata is now retrieved from the backend for the selected case; source choices are displayed by document label/page, including after reconnect.
6. Add a business requirement; `explicit` classification requires source UUID. `inferred` and `unverified` remain unconfirmed/proposed.
7. Select a requirement to fetch manager-only review history, review-version and rationale. A manager can submit rejection or confirm an explicit source-backed requirement with at least eight characters of rationale.

## Integration
The API uses absolute same-origin paths, e.g. `/v1/tenants/{tenantId}/research-cases`. Normal cookie-mode requests send same-origin credentials and `X-CSRF-Token` on mutations; they **never put Authorization bearer headers into browser JavaScript**. The pilot-only mode still uses bearer headers. The Vite development server listens on loopback only. For disposable developer testing, `DISCOVERY_API_ORIGIN=http://127.0.0.1:8000` can set a loopback-only development reverse proxy. Production hosting requires TLS + trusted same-origin BFF gateway, configured OIDC provider/JWKS/PKCE callback, CSRF enforcement, rate limits, logging redaction, deployment policy and application-level registration. The cookie BFF and OIDC callback adapter are implemented but no production provider/deployment is configured.

### Local syntax/build checks
```sh
cd web/discovery
npm install --no-audit --no-fund
npm test
npm run build
VITE_DISCOVERY_AUTH_MODE=pilot DISCOVERY_API_ORIGIN=http://127.0.0.1:8000 npm run dev
```
For the synthetic pilot server, migrations 0001–0011 are used; for cookie BFF tenant selection, migration 0012 is also required. The BFF must run with a configured trusted HTTPS origin and server-managed CSRF key. No backend deployment or live IdP integration is performed in this slice, and no fake customer-data fallback exists.

## UX acceptance
- Japanese-default labels, muted three-area layout: case navigation, requirements/evidence and review detail.
- Responsive single-column mobile layout at ~390px; keyboard focus, labels, aria-status/alert, text contrast, reduced motion. This is a preliminary accessibility implementation, not a certified WCAG 2.2 AA audit.
- Shows empty/loading/denied/conflict states. No autosave, no offline persistence and no protected file uploads.
- All mutations require a live backend response; do not claim a write succeeded before HTTP response.
- Pending write state only in browser memory. A reload mid-flight loses that state; for robust retry, add server-assisted reconciliation and durable client operation IDs before production.

## Known gaps / next acceptance
- In cookie mode, tenant choices are loaded from the server and no UUID input is required; pilot mode still intentionally uses test UUID/token. Authorized creation sites are also fetched from the backend.
- Source metadata listing is available with cursor pagination, but no raw document retrieval, document update or backend global search exists.
- No user-facing formal customer consent or signed decision workflow.
- No deployed customer-ready IdP configuration or production-grade login E2E. Real Chromium browser tests verify the synthetic, explicitly enabled pilot path; HTTPS IdP callback + cookie gateway deployment still needs separate E2E acceptance.
- Not allowed for real customer documents, tokens or personal information until the platform security acceptance is complete.

Architecture remains L1 Business & Experience → L2 Domain & Application → L3 Platform & Infrastructure. This frontend is L1 and reuses existing L2/L3 services without modifying their trust boundaries.
