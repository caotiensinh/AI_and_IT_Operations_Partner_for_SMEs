# Spec 020 — Trusted IdP freshness verification foundation

## Product outcome
An owner action must not be authorized by merely possessing a valid session or an arbitrary MFA flag. A signed OIDC ID token must prove a **fresh authentication event** for precisely the identity that owns the existing tenant session. The short-lived single-use database proof mechanism from Spec 019 is reused, not rebuilt.

## Architecture (L1–L3)
- **L1:** No customer approval screen or public callback introduced here; a future browser challenge uses the already-established PKCE/OIDC transaction infrastructure once its dependency chain has been integrated.
- **L2:** `verify_fresh_stepup` accepts a signed RS256 ID token from a pinned, preconfigured JWKS/issuer/audience. It requires a strong MFA signal, explicit verified `auth_time` within 120 seconds, nonce equality, and exact identity match against trusted session-backed issuer/subject. A new token `iat` alone cannot demonstrate reauthentication.
- **L3:** `resolve_asahi_stepup_identity(digest,tenant)` verifies active tenant, membership, unexpired/unrevoked session and tenant owner role; it returns only the bound issuer/subject, exposed exclusively to `sme_stepup` NOLOGIN. It does not disclose session tables or grant general runtime access.

## Security contract
The future trusted server must independently create, persist, and **atomically consume** a high-entropy browser-bound OIDC state/nonce challenge, use provider-pinned Authorization Code + PKCE, and fetch the expected issuer/subject from L3 for the same session+tenant before invoking `verify_fresh_stepup`. Only a successful assertion may invoke the isolated Spec 019 proof issuer. Never take expected identity, MFA status, JWKS URLs, or challenge nonce from user-controlled claims or inputs. Both issuer and approval roles remain NOLOGIN.

## Tests
- Signed synthetic-IdP token: accepted correct MFA, matching subject, issuer, nonce, and explicitly recent `auth_time`.
- Reject missing/stale/future/ill-typed `auth_time`, forged signature, wrong identity, token issuer, nonce, MFA evidence, stale/expired token, invalid time settings.
- PostgreSQL: only `sme_stepup` can resolve subject; foreign tenant, invalid session, revoked session and lost owner role fail closed.
- CI: all relevant jobs must pass on the exact PR HEAD before merging.

## Remaining before production
- [ ] Browser-bound, single-use state/nonce persistence and consumption with verified code exchange and trusted role mapping.
- [ ] Concrete HTTPS cookie BFF approval API with Origin/CSRF/SameSite and rate limits.
- [ ] Real IdP step-up with provider-documented `auth_time` / `acr` semantics and fresh MFA policy.
- [ ] Deployment of separately credentialed `sme_stepup` service only after independent security review.
- [ ] Customer end-to-end approval and external delivery acceptance.

**Status:** This slice implements verification primitives and database identity binding only; it does not create a production MFA endpoint, issue production proofs or send alerts. Existing stacked OIDC/Discovery PRs are separate and must be merged in dependency order.
