# Spec 023 — Opt-in secure Asahi owner approval BFF

## Objective
Close the application transport gap around Spec 022 without enabling customer-facing owner approvals by default. Reuse the existing secure session cookie and per-session CSRF contract; reconstruct all callback action parameters exclusively from the persisted, session+browser-bound database challenge.

## Architecture
- **L1 Browser:** POST owner-intent to `/v1/tenants/{tenant_id}/itops/asahi/stepup/start` using existing `__Host-sme_session` cookie, exact trusted `Origin` and `X-CSRF-Token`; redirects to pinned OIDC authorization endpoint. Never accepts Authorization bearer as a replacement for browser cookie.
- **L2 Trusted BFF:** separate `__Host-sme_stepup_bind` Secure/HttpOnly/SameSite=Lax cookie. Callback `/auth/asahi/stepup/callback` reads server-side session and cookie, accepts only IdP `state` and `code`. It does **not** trust incoming tenant, action, references or return URL; action comes from `sme.lookup_asahi_stepup_challenge`. Calls signed MFA verifier and one-time proof issuer through existing Spec 022 library. Proof is consumed through a separately authorized `sme_approval` connection.
- **L3 Database:** migration `0022` adds a scoped, read-only challenge lookup for NOLOGIN `sme_stepup`. Existing session, owner RBAC, action payload matching, replay prevention, and audit triggers remain enforced by PostgreSQL.

## Operational safety
- The new routes return HTTP 503 **unless explicitly opted in** via `enabled=True` and injected trusted callbacks. No default credentials, no auto discovery of IdP URLs, no hardcoded session keys.
- No production role grants, real IdP credentials, secret manager or outbound notification delivery.
- All cookie responses use `Secure`, `HttpOnly`, `SameSite=Lax` and `Cache-Control: no-store`. Production must terminate HTTPS correctly; client scheme behind reverse proxy must be pinned and validated by ingress.
- Errors are generic. POST requires exact Origin + CSRF. Caller must not expose CSRF key to users or reuse the migration owner as runtime DB role.
- No in-memory rate limiter is presented as cross-instance security; production ingress or shared store throttling remains a gate.

## Acceptance
- [x] Browser POST cookie only, fixed HTTPS origin and CSRF validation, wrong origin and missing session denied.
- [x] Callback fetches only persisted action under the same session and browser binding, no query payload or open redirect.
- [x] Proof passed to separate executor; replay cannot execute twice, audit remains one record.
- [x] Direct SQL lookup from sme_app, auth, ingest, dispatch, approval roles is denied.
- [x] Opt-in default disabled; failing callback clears binding cookie.
- [ ] GitHub Actions integration/identity/unit/browser/compose all PASS on final PR commit.
- [ ] Real IdP/HTTPS browser navigation with external provider credentials.
- [ ] Distributed rate limiting, CSRF secret rotation, hardened ingress proxies, observability and multi-instance exercise.
- [ ] Independent least-privilege production service principals and customer acceptance before enabling feature.

## Dependencies
The existing OIDC/Discovery pull-request stack remains separate, and must be merged only in dependency order. No changes to those branches are made here.
