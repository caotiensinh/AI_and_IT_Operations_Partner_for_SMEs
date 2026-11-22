# Spec 022 — Asahi trusted OIDC MFA step-up orchestrator

## Goal
Integrate *existing* signed OIDC MFA freshness verification (Spec 020) with durable browser-bound one-use PKCE challenges (Spec 021) and action-bound approval proofs (Spec 019). This is a trusted **L2 service library**, not a public API.

## L1–L3
- **L1** future HTTPS BFF: obtains session from server-managed secure cookie, resolves tenant from authenticated authorization, creates server-side owner action; creates a separate HttpOnly SameSite browser binding cookie. Never trusts browser-supplied session digest or target IdP URL.
- **L2** `AsahiStepupOIDCFlow.start`: CSPRNG state, browser binding, nonce, PKCE verifier; persists SHA-256 state/browser digests and session+tenant+payload via `PostgresStepupStore`; produces operator-fixed authorization URL with `prompt=login`, `max_age=0`, nonce and PKCE S256 challenge.
- **L2** `complete`: validates code and browser/state formats, atomically consumes the correct persisted challenge, re-resolves expected IdP identity from active owner session, exchanges authorization code with configured trusted token endpoint (injected adapter), validates signature, issuer, audience, nonce, actual `auth_time` and MFA, then issues Spec 019 single-use action-bound DB proof. On failure no proof is issued and challenge cannot replay.
- **L3** `sme_stepup` dedicated NOLOGIN service role; no raw session/challenge/proof table grants. Existing approval DB functions remain protected by separate `sme_approval` role.

## Acceptance
- [x] Synthetic signed IdP full start → PKCE → callback → MFA check → proof.
- [x] Correct PKCE SHA-256 challenge and pinned client/redirect.
- [x] Reject wrong browser, state, tenant, session, action, destination, nonce, MFA, stale auth_time, signature or revoked owner.
- [x] Challenge consumed at most once, including after rejected MFA.
- [x] Real PostgreSQL store begin/consume/identity/issue roundtrip and proof consumption regression.
- [ ] All CI checks PASS on exact PR HEAD before merge.
- [ ] Connect independently configured IdP token exchanger with actual HTTPS browser callback + bound cookie and CSRF/Origin/rate limit enforcement.
- [ ] Deploy least-privilege service credentials reviewed separately, no general app role grant.
- [ ] Production IdP validation and customer approval E2E through UI.

## Deployment boundary
The injectable `exchange_code` callback must be an independently pinned OIDC token exchange adapter. This PR does NOT create a public callback/API, deploy a service, load production IdP configuration, provision secrets/roles, or send alerts. Server has to bind callback parameters to the *original server-side stored owner action*, not accept a caller-chosen tenant/action/destination from query parameters. A token `iat` does not prove recent reauthentication; the verifier requires signed `auth_time`. Challenge deletion occurs before token exchange; retried callbacks fail closed.
