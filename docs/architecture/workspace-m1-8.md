# M1.8 — Responsive workspace + tenant selector pilot

- Backend provides active accessible tenants from the currently authenticated opaque session.
- Browser session cookie is accepted for safe GET asset listings and tenant selector (bearer header remains for legacy pilot).
- PostgreSQL audit remains transactionally enforced for successful asset listings.
- Responsive React app: left sidebar desktop, compact tablet layout, mobile bottom navigation, explicitly selected tenant, accessible asset table, loading/error/empty states.
- No mocked business data: unavailable modules/incident services render neutral placeholders.
- Security acceptance: A's cookie cannot read B assets; forged cookie cannot enumerate tenants; session revocation takes effect on the next API call.
- Next: authenticated OIDC browser E2E, Vite build CI, WCAG keyboard/mobile visual tests, strict CSP/headers, translation and service module integration.

This pilot is NOT production-ready. Do not share data externally until session issuance and browser APIs are integrated behind HTTPS with real provider tests.
