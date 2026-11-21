# CSRF issuance must require an active session

## Root cause
The browser gateway previously returned HMAC-derived CSRF tokens solely on
a 43-character cookie, without looking up session revocation/expiry.
This was not an authorization bypass for logout but exposed a valid-looking CSRF
token for an expired/revoked or forged session.

## Remediation
- Require an injected `session_active(token)` callback in browser gateway.
- Add restricted `sme.session_is_active(SHA256(token))` SQL function.
- The trusted runtime adapter, not the browser, calls the database function
  through `sme_app`.
- Deny CSRF issuance and logout when callback indicates inactive session.
- Tests include valid, revoked/forged and logout-denied negative paths.

## Limits
No browser gateway mounted to production API yet. Application must wire the
validator to PostgreSQL, expose TLS, and review CSRF handling for all state-changing
browser endpoints before any real login launch. Function only verifies whether
a session is active in at least one tenant; it never returns tenant information.
