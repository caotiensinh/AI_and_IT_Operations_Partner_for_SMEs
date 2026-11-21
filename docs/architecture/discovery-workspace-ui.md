# Business Discovery Workspace — UI slice 024

**Scope:** A real, Japanese-first React/TypeScript/Vite browser client for the already-tested discovery API. Not a production-ready login or customer-facing SaaS.

## User workflow
1. Enter a *synthetic/test* tenant UUID and opaque bearer session token obtained from the disposable environment. The token is held only in React memory, never in localStorage, sessionStorage, URL/query string, cookies, or source code. Disconnect clears state. Reload requires reconnect.
2. Read site/tenant-authorized case list. UUID cursor pagination follows backend `next_cursor`; search filters only currently loaded items, not a global backend search.
3. Create case by selecting an authorized site label (provided by the backend) and company archetype; use a stable `Idempotency-Key` until the logical create has returned. A failed request may be retried with the same key while form content stays unchanged.
4. Select case, read paginated requirements, see classification, approval state and source label/page.
5. Register metadata-only evidence source (label, page, client-generated UUID). Existing source metadata is now retrieved from the backend for the selected case; source choices are displayed by document label/page, including after reconnect.
6. Add a business requirement; `explicit` classification requires source UUID. `inferred` and `unverified` remain unconfirmed/proposed.
7. Select a requirement to fetch manager-only review history, review-version and rationale. A manager can submit rejection or confirm an explicit source-backed requirement with at least eight characters of rationale.

## Integration
The API uses absolute same-origin paths, e.g. `/v1/tenants/{tenantId}/research-cases`, with browser `fetch` and Authorization header. The Vite development server listens on loopback only. For disposable developer testing, `DISCOVERY_API_ORIGIN=http://127.0.0.1:8000` can set a loopback-only development reverse proxy. Production hosting requires TLS + trusted same-origin gateway, OIDC/PKCE callback, secure browser sessions, CSRF protections where applicable, rate limits, logging redaction, deployment policy and application-level registration; **none** are provided by the UI slice.

### Local syntax/build checks
```sh
cd web/discovery
npm install --no-audit --no-fund
npm test
npm run build
DISCOVERY_API_ORIGIN=http://127.0.0.1:8000 npm run dev
```
API server must already be running with a disposable PostgreSQL instance and migrations 0001–0011; no backend deployment is performed in this slice. The UI cannot independently mint a real session. There is no artificial 'demo' data fallback.

## UX acceptance
- Japanese-default labels, muted three-area layout: case navigation, requirements/evidence and review detail.
- Responsive single-column mobile layout at ~390px; keyboard focus, labels, aria-status/alert, text contrast, reduced motion. This is a preliminary accessibility implementation, not a certified WCAG 2.2 AA audit.
- Shows empty/loading/denied/conflict states. No autosave, no offline persistence and no protected file uploads.
- All mutations require a live backend response; do not claim a write succeeded before HTTP response.
- Pending write state only in browser memory. A reload mid-flight loses that state; for robust retry, add server-assisted reconciliation and durable client operation IDs before production.

## Known gaps / next acceptance
- No tenant picker (tenant UUID is still manually supplied in the pilot); the creation-site picker is now populated by a permission-scoped backend endpoint.
- Source metadata listing is available with cursor pagination, but no raw document retrieval, document update or backend global search exists.
- No user-facing formal customer consent or signed decision workflow.
- No production-grade OIDC frontend login, no end-to-end Playwright test with a real browser yet, no deployed environment.
- Not allowed for real customer documents, tokens or personal information until the platform security acceptance is complete.

Architecture remains L1 Business & Experience → L2 Domain & Application → L3 Platform & Infrastructure. This frontend is L1 and reuses existing L2/L3 services without modifying their trust boundaries.
