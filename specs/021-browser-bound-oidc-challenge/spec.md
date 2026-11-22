# Spec 021 — Browser-bound, single-use OIDC step-up challenge

## Goal
Persist a one-time OIDC state/nonce and PKCE verifier for an Asahi owner approval, bound to the originating browser, current session, tenant, action and exact opaque destination references. This closes the gap between the signed IdP MFA verifier (Spec 020) and the single-use approval proof (Spec 019).

## Architecture
- L1: future HTTPS browser BFF generates high-entropy `state`, `browser_binding`, `code_verifier`, `nonce`; sends SHA-256 state/browser digests to database. **No frontend or HTTP callback in this PR.**
- L2: the trusted MFA service obtains fixed IdP configuration and code-exchange endpoint; starts challenge only after owner session verification and consumes it atomically at callback before token exchange and signature/auth_time checks.
- L3: `sme.asahi_stepup_challenges` stores only state/browser/session **digests**, action-bound opaque references, verifier and expected nonce. Restricted NOLOGIN `sme_stepup` begin/consume SQL functions; no regular application direct table rights.

## Acceptance
- One state may be consumed at most once even under two concurrent clients.
- Wrong browser binding, session, tenant, action or references never returns verifier/nonce and never consumes the correct challenge.
- Expired challenge or revoked session cannot be consumed.
- Runtime roles (`sme_app`, `sme_auth`, `sme_dispatch`, `sme_ingest`, `sme_approval`) cannot invoke begin/consume.
- On successful callback only the matched record is deleted; stale entries remain for future privileged expiry cleanup.
- All CI including PostgreSQL integration PASS on final PR HEAD before merge.

## Explicit exclusions and risk
The DB validates digest sizes and safe input formats but cannot attest the randomness of caller-supplied secrets. The future trusted BFF must use CSPRNG and securely bound cookies; must never accept attacker-selected state, nonce, verification endpoint, role or issuer. This PR does NOT perform OIDC Authorization Code + PKCE exchange, validate MFA, issue a proof, connect production role credentials, or expose a customer approval UI. Those integration and actual IdP acceptance tests remain outstanding. Do not authorize live sending on this basis.
