# M1.5 — OIDC Authorization Code + PKCE transaction kernel

## Implemented
- Server-generated cryptographically random state, per-browser binding secret, nonce and 64-character PKCE verifier.
- SHA-256 PKCE S256 challenge; fixed HTTPS authorization endpoint, client ID and redirect URI.
- Pending login stored centrally in PostgreSQL with hashed state/browser binding, five-minute expiry, and atomic single-use consumption.
- Strict OIDC ID-token validation, including nonce after signed JWT validation, then internal (issuer,subject) identity lookup.
- Session issuance restricted to dedicated `sme_auth` database role; runtime `sme_app` cannot issue sessions or read pending login/session tables.
- Authentication rejected when no active membership in an active tenant.
- Positive and negative unit tests plus PostgreSQL 16 integration tests.

## Security model
```text
Browser (start) -> random state + binding cookie -> authorization URL
  -> configured OIDC provider (code + PKCE S256 + nonce)
  -> browser callback -> one-time DB consume(state_hash,binding_hash)
  -> trusted server token exchange (external adapter, not implemented)
  -> verify ID-token signature, issuer, audience, nonce, time, MFA
  -> map issuer+subject to internal active identity
  -> dedicated auth role issues opaque session digest
  -> existing tenant API validates session + membership + RBAC + RLS
```

## Must NOT claim complete
- No live OIDC provider login or token exchange HTTP client; tests inject a synthetic signed issuer.
- No callback HTTP endpoints or secure HttpOnly/SameSite browser cookie lifecycle yet.
- No OAuth token endpoint discovery / pinned HTTP TLS config / JWKS refresh, PKCE state redirect E2E with real provider.
- No session rotation and CSRF protection, rate limiting, failed-login audit, anti-automation checks or live identity provisioning.
- The DB role `sme_auth` is NOLOGIN in schema; production requires separate least-privilege LOGIN principal with exact permitted function executions and secret provisioning.
- Current auth module returns a bearer token for integration with existing protected API; browser session cookie and logout/CSRF policy remain to be implemented before public UI.
- No private customer data, account, identity provider, camera or legacy adapter enabled.

## Tests
`PYTHONPATH=src python -m unittest discover -s tests -v`

GitHub Actions PostgreSQL 16 integration workflow is source of truth for DB tests. CI test success is not production readiness.

## Next incremental deliverable
M1.6 — pinned token exchange client, authentication callback handler with browser cookies, OIDC provider emulator test, CSRF-safe session/logout behavior, logout and audit. Then independent security review and pilot deployment.
