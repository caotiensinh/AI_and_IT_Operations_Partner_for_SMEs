# M1.3 OIDC identity-token verifier (initial increment)

## Purpose and boundaries
This module verifies **OIDC ID tokens only for login bootstrap** using a trusted pinned JWKS, configured HTTPS issuer, client ID and RS256. It validates signature, issuer, audience/azp, subject, issued/expiration timestamps, token age, MFA policy (amr, provider-specific allowed acr), and ignores untrusted key-fetch URLs from token headers.

### Identity ≠ authorization
- The OIDC subject is a **provider identity**, not an SME tenant. Never derive tenant ID/roles/sites from ID token claims or form input.
- Resolve (issuer,sub) against trusted internal `sme.identities` and `memberships`; check status, role, scope and explicit tenant choice after authentication.
- Never pass an ID token as an API bearer credential. API requires first-party short-lived session / OAuth access token validation, CSRF-safe cookie strategy and logout/revocation.
- Provider JWKS download/rotation must be implemented by trusted infrastructure using pinned discovery URL and strict timeouts/caching, never via user-supplied header URL.
- Real redirect/callback, PKCE, state, nonce, provider MFA assurance validation and session persistence are NOT implemented in this increment.
- There is no tenant user login flow or UI yet.

## Threats covered by the verifier
Forged signature, wrong issuer/audience, expired/stale/future timestamp, missing subject, untrusted signing-key URL, unknown signing key, rejected MFA and mismatched azp.

## Deployment restriction
Not production deployable alone. Must complete OIDC authorization-code + PKCE + state + nonce flow, MFA policy and secure session lifecycle, audited membership lookup, tenant-bound API tests and connection pooling tests before any customer login.
