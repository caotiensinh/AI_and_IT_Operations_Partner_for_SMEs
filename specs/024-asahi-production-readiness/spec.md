# Spec 024 — Production Security & Deployment Readiness Gate

## Objective
Keep the Asahi owner approval feature **OFF** unless an operator explicitly confirms required production controls and an independently privileged runtime database check proves that issuing an MFA proof cannot be confused with consuming it. No hard-coded credentials or implicit authorization.

## Architecture
- **L1:** Existing HTTPS owner BFF remains disabled by default. Explicit enablement now *requires* a startup preflight callback; failures abort route installation.
- **L2:** `StepupProductionConfig.validate()` inspects fixed HTTPS public origin, matching same-origin callback path, pinned same-provider authorization/token endpoints, true RSA public keys and approved enterprise OIDC client, 32+ byte signing key, independent PostgreSQL DSNs with exact `sslmode=verify-full`. All four operator reviews must be true: IdP MFA contract, TLS ingress, distributed rate limiting, and secret provisioning.
- **L3:** `verify_production_stepup_connections` probes **the actual configured DB connections**, verifies no superuser/bypass/role creation power, separate logins and exact positive/negative function/table privileges. Issuer must have begin challenge, resolve session identity and issue proof but no ability to approve; approver must approve via proof but may not issue proofs or inspect sensitive tables.

## Acceptance
- [x] Correctly configured synthetic production deployment and separate least-privilege connections accepted.
- [x] Missing reviews, malformed HTTPS endpoints, mismatched OIDC provider, non-RSA JWKS, inadequate CSRF secret, reused DB connection, missing verified TLS, privileged roles or extra table/function privileges rejected.
- [x] Enabling BFF with missing or failing preflight raises before routes are registered. Disabled mode stays available without invoking production credentials.
- [ ] All CI jobs PASS on exact PR HEAD, and merge after fresh main/PR verification.
- [ ] Operated real provider configuration and signer verification through actual browser and IdP.
- [ ] Real TLS reverse proxy, X-Forwarded-Host enforcement, edge WAF, distributed rate limiting, certificate pinning/policies, secure secret vault and secret rotation acceptance.
- [ ] Test real least-privilege PostgreSQL login principals with `sslmode=verify-full`, ephemeral environment and recovery.
- [ ] Customer acceptance for approval, revocation, audit, lease/idempotency and outbound delivery.

## Security disclaimer
Flags record operator attestation; they are NOT proof that ingress, IdP MFA policy or rate limiting are correctly deployed. A config + DB preflight pass is only a prerequisite. Privilege inspection uses the real login's `session_user`; a privileged migration owner with `SET ROLE` must not be considered production readiness. No production credentials, secrets, live provider or HTTP deployment is included here. Existing staging Compose remains loopback-only HTTP and **must not** enable this feature.

## Rollback
Do not activate approval until end-to-end operations acceptance. If an active deployment fails a preflight, leave the approval feature disabled; preserve DB audit history and existing alert policies. Revoke separate login principals rather than deleting evidence.
