# Spec 003 — Enterprise OIDC Deployment Preflight (slice 035)

## Purpose
Prevent deployment of the SME Discovery cookie BFF based only on a green synthetic-IdP test. A production-like rollout requires a **read-only, fail-closed check** of operator-provided configuration, provider metadata/JWKS, HTTPS callbacks, MFA policy and actual database-role grants. The command returns a JSON evidence summary containing **check IDs and sanitised outcomes only**, never credentials, connection strings or JWTs.

## Command and contract
From a runtime provisioned through a Secret Manager, with real operator-issued credentials:

```bash
PYTHONPATH=src python -m sme_partner.oidc_preflight
```

Exit code **0**: all mandatory checks passed. Exit code **1**: configuration, IdP reachability, credential or DB permission check failed. Output: `{"ready":true|false,"checks":[{"name":"...","passed":true|false,"detail":"..."}]}`. Keep this output in the deployment change record, with timestamp, release SHA and reviewer identity **outside** the public repository. Never paste the underlying environment or client credentials.

This tool performs **no session creation, authorization code issuance, database writes, migrations or browser login**. Provider GET requests use fixed HTTPS endpoints, TLS validation, a 5-second bounded timeout, capped JSON responses and no automatic redirects.

## Gate matrix (all mandatory for READY)

| Gate | Acceptance |
|---|---|
| `config.required` | All eleven operator configuration variables supplied (names only) |
| `config.database_split` | Application/auth connection strings differ |
| `config.csrf` | Server-secret is valid hex and at least 32 bytes |
| `config.origin`, `config.callback` | Fixed HTTPS origin; exact `/auth/oidc/callback` match |
| `config.mfa_policy` | Production-like onboarding explicitly requires MFA |
| `provider.pinned` | Provider endpoints, client registration and callback parsed/validated |
| `provider.discovery` | Metadata fetched over HTTPS and matches all pinned endpoints; supports code, RS256 and PKCE S256 |
| `provider.jwks` | RSA public keys have valid structure, unique IDs and permitted signing algorithm |
| `db.sme_app.identity` | Dedicated non-superuser, non-BYPASSRLS application DB login; can SET only `sme_app` |
| `db.sme_auth.identity` | Dedicated non-superuser, non-BYPASSRLS auth DB login; can SET only `sme_auth` |
| `db.sme_app.*` | Can list session tenants through tightly scoped function; cannot issue OIDC sessions, start auth login or SELECT raw sessions/pending logins |
| `db.sme_auth.*` | Can begin/consume OIDC login and issue sessions; cannot list session tenants nor SELECT raw credentials/tables |

A rollout is **never marked READY if the provider network or DB permission checks are skipped**, even when all offline syntax/format tests pass. The test-only `check_network=False` / `check_database=False` flags exist for isolated unit tests; do not use them for operational acceptance.

## L1/L2/L3 evidence boundaries
- L1 (browser): No interactive user login is performed by this command. Full enterprise IdP user login, MFA proof, callback, logout and user/tenant acceptance remain manual canary gates.
- L2 (BFF): TLS public origin, pinned external metadata and signing key checks pass; route deployment, WAF, rate limits, CSP/HSTS, trusted proxy headers, runtime secret renewal, audit/alerting and rollback still require operational signoff.
- L3 (PostgreSQL): Both provided login credentials are checked through **read-only SQL transactions**, including actual ability to assume only their assigned SME role, privilege boundaries on SECURITY DEFINER functions, and denial of raw credential-table SELECT.

## Failure and recovery
Any failed gate blocks the rollout. Inspect only the corresponding stable gate ID, correct the **source** of the configuration/role/provider defect, rerun this command and capture a new result. Never relax role privileges, disable PKCE/MFA or suppress cert verification to force readiness. Timeout or unavailable IdP is **UNKNOWN operational state**, reported as a failed gate; it is not proof the provider is broken or that the deployment is ready.

## Scope and deployment limitations
A green preflight only verifies the specified controls at the instant executed. It **does not** attest to a trusted HTTPS deployment, actual enterprise identity authentication, approved client secret registration, token-endpoint behaviour under real load, user-consent flow, organization-specific MFA policy, certificate chain deployed to browsers, credential rotation, operational monitoring, backups or a penetration test. No customer data are used in CI. This slice is stacked after PR #53; no changes are merged into `main` automatically.
