# Spec 018 — Isolation gate for owner approval service

## Current objective
Prevent the general `sme_app` runtime identity from invoking Spec 017 approval/revocation stored procedures while a production MFA step-up proof is **not** connected.

## Acceptance
- [x] Add `sme_approval` as a dedicated `NOLOGIN`, `NOBYPASSRLS` role without raw table grants.
- [x] Revoke approval function EXECUTE from `sme_app`, `sme_auth`, `sme_ingest`, `sme_dispatch`, and PUBLIC.
- [x] Allow only `sme_approval` to execute approval/revocation functions; existing active-session and owner RBAC remain enforced inside the functions.
- [x] PostgreSQL tests cover the positive dedicated-role path and negative app/auth/ingest/dispatch access.
- [ ] Verify all CI workflows green on exact revision, then merge.
- [ ] Implement IdP-backed fresh MFA/step-up, action/tenant/session binding, one-time consumption, replay prevention and time bounds.
- [ ] Provision authorized separate service login mapped to `sme_approval` ONLY after security review; do not grant membership to general app or auth logins.
- [ ] Add HTTPS + CSRF + origin checked BFF/API and browser E2E; no production owner UI until the above gates pass.

## Security considerations
This is a **hardening step**, not completion of MFA or production approval. The narrowly privileged NOLOGIN role can be assumed by a privileged administrator in tests; production must never grant it to the generic app connection. Role and session binding alone do not prove fresh MFA. The database migration executor retains administrative authority. Outbound notifications and customer credentials remain disabled.
