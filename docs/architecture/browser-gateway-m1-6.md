# M1.6 — Browser authentication transport (HTTP slice)

## Implemented
- Fixed HTTPS public origin, no arbitrary callback redirects.
- `GET /auth/start`: login transaction, OIDC authorization redirect, 5-minute Secure/HttpOnly/SameSite=Lax `__Host-` browser-binding cookie.
- `GET /auth/callback`: validates browser-bound one-time state and signed ID-token via the underlying flow; sets Secure/HttpOnly/SameSite=Lax `__Host-` opaque session cookie.
- `GET /auth/csrf`: returns per-session HMAC CSRF token with no-store.
- `POST /auth/logout`: strict Origin + HMAC CSRF check, server-side revocation callback and cookie deletion.
- Pinned HTTPS token endpoint exchange adapter, redirects disabled, response size and timeout bounded.
- Unit tests include malicious origin, CSRF, missing cookie, invalid state and token exchange failures.

## Not production complete
1. Integration route wiring must supply a dedicated least-privilege `sme_auth` connection separate from `sme_app`.
2. Existing /v1 assets API still accepts header bearer tokens; browser-cookie authentication for resource API and explicit CSRF safeguards for all mutating browser endpoints remain open.
3. JWKS trust bootstrap, rotation, live OIDC provider test and HTTPS deployment are still open.
4. Rate limiting, revocation checking for CSRF retrieval, trusted proxy headers, session rotation, multi-device management, audit, strict CSP and threat model remain open.
5. The start/callback test uses a fake flow. Cryptographic OIDC and DB issuance are verified in separate suites, not yet a single real-provider browser E2E.
6. Do not expose the service to customer traffic until full authentication E2E and security review.

## Next
M1.7: audit events and authenticated tenant context, then M1.8: real responsive workspace connected to protected API.
