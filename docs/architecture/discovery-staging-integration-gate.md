# Spec 003 — Staging Integration Gate and Safe Release Procedure (slice 036)

## Goal
Turn individually verified, stacked Business Discovery/OIDC pull requests into a reproducible **read-only integration acceptance**. This gate **does not merge or deploy**. It records the current expected GitHub source state, checks the actual open PR topology and CI on the exact final PR SHA, and refuses acceptance on missing/failed/stale evidence.

## L1/L2/L3 release boundaries
- **L1 Experience:** Japanese Discovery Workspace and pilot Chromium tests, HTTPS cookie-mode E2E, and synthetic RSA/PKCE OIDC browser E2E. These validate independent workflows; a real corporate IdP user login is NOT covered.
- **L2 Domain/Auth:** tenant-scoped Discovery API, reviews/history, OIDC callback, HttpOnly cookie BFF, CSRF guards, pinned provider client, limited JWKS rotation and deployment preflight. Real IdP configuration/registration and security signoff remain external requirements.
- **L3 Platform:** PostgreSQL 16 migrations, RLS, constrained `sme_app` and `sme_auth` database roles, synthetic database/role tests. Secrets and real service hosts must be provisioned outside GitHub by the operator.

## Immutable evidence and checks
Manifest: `specs/003-sme-business-needs/integration-chain.json`.

Command from a trusted project checkout:

```bash
PYTHONPATH=src python -m sme_partner.integration_gate \
  --manifest specs/003-sme-business-needs/integration-chain.json
```

The command fetches **read-only GitHub API** data. For a private repository, supply a short-lived `GITHUB_TOKEN` with only **Contents:read, Pull requests:read, Actions:read**. Never print the token or embed it in scripts or manifests. It validates:

1. Every listed PR is open, not merged, from the expected repository, exactly at its recorded 40-character head SHA, and reported mergeable by GitHub.
2. Each stacked PR points to the preceding PR's **actual branch name and exact head SHA**, rather than just being mergeable against a drifting branch.
3. The last PR's configured required workflows have completed with **success on its exact SHA**, never a previous source commit. Pending, failed, absent or inaccessible evidence blocks approval.
4. JSON has `ready`, `terminal_sha`, stable check names, pass/fail values and non-sensitive messages. The terminal exit code is 0 only when the whole gate succeeds.

The checked PR list currently starts at #19 and runs through #55. **Prerequisites before #19 are not within this manifest and must be separately audited**. This gate also does not test the `main` merge result or account for branches updated after the check; rerun after any change, and independently run integration checks on a merged staging candidate before release.

### Snapshot and freshness
The manifest pins an evidence snapshot. It deliberately goes stale if any listed source branch changes or if any PR is merged/closed. Update it only after inspecting the changed branch, reproducing required tests and reviewing the delta. Never automatically rewrite the manifest with whatever GitHub currently returns; that would defeat the pinning.

GitHub Actions: `Discovery integration readiness gate` uses the same read-only API, with a restricted `GITHUB_TOKEN`; network failures are FAIL/UNKNOWN, not PASS. No token or private URLs appear in the result summary.

## Staging procedure (operator approval required)
1. Verify which open PRs are required, their logical order and their dependency state. Include unlisted earlier PRs, which are **outside** the current gate.
2. Review authentication, RLS, DB migrations and role grants with an independent reviewer. Review idempotency, sensitive logging and tenant isolation regressions.
3. Re-run the integration gate at the exact candidate SHA. Inspect all relevant workflow runs and compile a deployment evidence record including hashes, reviewer, risk assessment and rollback plan.
4. Prepare staging-only TLS domain and trusted certificate, network egress policies, secrets manager, separated PostgreSQL service roles and an **empty/disposable** staging database. Never use production customer data.
5. Run schema migration/role checks against staging. Run `python -m sme_partner.oidc_preflight` with the operator-authorized provider and database configuration. Its `ready=true` is necessary but not sufficient.
6. Create a controlled staging integration branch following reviewed PR dependencies, **only after explicit maintainer authorization**. No automated PR merge or force-push. Preserve the previous deployment version, database backups and tested restore path.
7. Test HTTP/SameSite/CSRF in a trusted real browser, authorizations of two independent tenants, failed state/token callback, logout/revocation, real provider consent/MFA and alerting. Verify all service roles cannot cross tenant or privilege boundaries.
8. If the smoke test fails, disable access to the new staging release, restore the previous application artifact, and evaluate whether the database schema is backwards compatible. **Never blindly downgrade** a migration that may lose data. Preserve logs and incident timeline; retry only after locating the failure.
9. Record operator signoff for release readiness; promotion to production requires a separate security and customer consent gate.

## Acceptance status and caveats
GitHub CI confirms a read-only **stacked PR compatibility snapshot** only. It cannot infer provider real-world authorization, regulatory compliance, customer data retention policy, rate limiting, certificate renewal, load capacity, SLOs, disaster recovery or penetration-test results. In particular, **do not treat a green synthetic IdP/CI run as approval for customer authentication**.

## Known release blockers
- Unreviewed and unmerged PR chain, including parent prerequisites before #19.
- No real company IdP registration, credentials, MFA validation and consent.
- No deployed public staging domain with certificate chain and reverse-proxy header trust.
- No audited database backup/restore, rate limiting, structured monitoring and incident response.
- No independent secure deployment/tenant-boundary review.

Do not claim "production-ready" until these gates have been independently completed and persisted.
