# Spec 026 — Synthetic signed IdP → HTTPS BFF → real PostgreSQL login acceptance

## Purpose
Validate the integration boundary that previously existed only in separate tests: browser-originated Asahi owner approval and revocation must succeed *only* after fresh signed MFA and must be executed using distinct password-authenticated PostgreSQL logins, not migration-owner `SET ROLE`.

## Scope and L1–L3
- **L1**: FastAPI HTTPS-origin `TestClient` exercises real BFF endpoints, session cookie, CSRF, state and browser binding. This does **not** establish TLS at a network ingress.
- **L2**: Synthetic in-process IdP signs RS256 ID tokens with an ephemeral RSA private key. The existing verifier checks signed `auth_time`, nonce and owner subject. PKCE and durable challenge/proof orchestration is the production library, not fake business logic.
- **L3**: PostgreSQL 16 service authenticates real `sme_stepup_e2e_login` and `sme_approval_e2e_login` using independent generated passwords. The first login creates/consumes challenge and issues a one-use proof; the second consumes the proof and records delivery policy audit. No change to production provisioning.

## Acceptance tests
- [x] End-to-end test authored with signed MFA, real DB login connections, approve → revoke and persisted audit assertions.
- [x] Tests authored for missing MFA, stale auth_time, forged state/tenant, revoked session and denied cross-role `SET ROLE`.
- [ ] PostgreSQL integration CI PASS on final PR commit.
- [ ] Remaining CI checks PASS on same commit where triggered; merge only with refreshed main SHA.

## Explicit limitations
- The IdP is synthetic and local. Network TLS termination, provider-signed real token, server-side client registration, production MFA policies and all external delivery remain **UNVERIFIED**.
- Test harness invokes `production_preflight=lambda:None` deliberately only under disposable CI database and ephemeral keys. It is never an authorization to deploy.
- Production BFF must still complete real preflight, provision separate credential stores with verified TLS, and use shared ingress rate limiting before enabling the feature.

## Conflict isolation
Work is isolated to a test and Spec Kit document. Concurrent Spec 026 governance PR #72 is not modified or merged out of order.
