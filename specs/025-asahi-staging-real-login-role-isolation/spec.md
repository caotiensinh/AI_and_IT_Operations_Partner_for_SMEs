# Spec 025 — Staging Password-Authenticated Step-up Role Separation

## Context
Specs 019–024 introduced scoped PostgreSQL security functions, a disabled-by-default owner BFF, and a production preflight. The prior staging Compose proved role permissions mainly by simulating `SET ROLE` from the migration administrator. That is insufficient to prove separate login credentials and runtime segregation.

## Goal and acceptance
Implement and test two distinct **disposable staging-only** password-authenticated PostgreSQL login principals:
- `sme_stepup_runtime` inherits only NOLOGIN `sme_stepup` and may issue a challenge/proof but not consume a proof or read its table.
- `sme_approval_runtime` inherits only NOLOGIN `sme_approval` and may consume approve/revoke proofs but not issue, inspect challenges or cross-assume the issuer role.
- Both can connect as separate PostgreSQL `session_user`, are non-superuser with no bypass/creation grants, and cannot directly mutate destination or inspect session/proof rows.
- No staged app container receives either credential, no production OIDC connection, and no actual email/webhook delivery is enabled.

## Implementation
- `bootstrap_stepup_roles.sql`: idempotent, independently passworded logins, split grants and explicit cross-role REVOKEs; stage operator uses psql variables to SQL-escape passwords.
- `migrate.sh`: runs role bootstrap after all migrations.
- `.env.staging.example` and `compose.staging.yml`: require two independent disposable secrets only in the migration service.
- `check_stepup_logins.sh`: authenticates each real login with its own password, checks `session_user=current_user`, positive/negative functions, denied sensitive table privileges, and rejected `SET ROLE` escalation.
- `staging-compose.yml`: generates two new random CI secrets and runs check against live PostgreSQL 16 after deployment.

## Security and scope limitations
This is an **isolated staging smoke** over the Compose private Docker network, not the Spec 024 production preflight; staging transport does not use `sslmode=verify-full`. Neither runtime login is passed to the API or published outside the private Docker network. Production still requires full TLS, a secret manager, distributed rate limiting, IdP MFA contract review, separate production service principals, real browser IdP E2E and owner acceptance. Do not set `enabled=True` for BFF on this basis.

## Verification gate
- [x] Code, bootstrap, workflow and checks committed on a dedicated branch.
- [ ] CI Compose + Integration + Unit + Identity + Browser PASS at the final head.
- [ ] Staging real-password checks PASS, including denied privilege escalation.
- [ ] Revalidate current `main` and merge head unchanged; confirm merge SHA.
