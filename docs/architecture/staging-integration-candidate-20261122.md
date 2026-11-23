# Staging Integration Candidate — 2026-11-22

## Scope and immutable review points

This candidate is **not the main branch, not a production deployment and not customer-ready**. It contains the complete Discovery/OIDC feature PR stack layered onto a pinned `main` snapshot including the concurrently developed Asahi modules.

- Staging branch: `integration/discovery-staging-20261122`
- First main snapshot: `778933534d167315144fc692d350ba1803b17e94`
- Discovery/OIDC stack HEAD: `a75015371c32e77a751c38a06a32d1166a1e08cf` (PR #61)
- First successful integration: `ab64a6293214974b8c0c91b173652ae0ea0fa347`
- Refreshed main snapshot: `4712bdefeead74275700bf47c2b6eab2c25e4149`
- Refreshed integration commit: `89fbab34ea8ca70092ae2af5fce96eeaf469ce28`
- Main has **not** been modified by this work. PR #63 was automatically marked merged after its feature HEAD became an ancestor of the isolated staging branch, **not main**.

## Root causes fixed in the staging candidate

1. The three-way merge had one textual conflict, `tests/test_discovery_postgres.py`. The 14 original main test functions were AST-equivalent in the feature version; the feature version retained all 14 and added 38 tests. The local integration workflow asserted this before choosing the superset file.
2. Main migrations `0005–0019` and feature migrations `0005–0012` reused numbers. The read model SQL was equivalent except its dependency comment. Canonical main migrations were preserved; Discovery additions were initially normalized to `0020–0026` for the first snapshot, then assigned a dedicated `0100–0106` domain range after main added Asahi migrations 0020/0021.
3. Main defined `sme.list_session_tenants(bytea)` with OUT column `display_name`; Cookie BFF defined the same function with `tenant_label`. PostgreSQL rejects an incompatible CREATE OR REPLACE return signature. The candidate retains the existing main API and gives BFF the distinct `sme.list_browser_session_tenants(bytea)` function. BFF/preflight tests and RBAC queries use the new function. No drops, weakened privileges or production data migration were used.

## Canonical schema on the refreshed candidate

- Shared tenant/security, Asahi and core read model: migrations `0001–0021`.
- Discovery write/source/review/cookie operations: `0100–0106`.
- Migrations are ordered by filename; the new domain range is **not contiguous with shared migrations**. Do not use a universal `range(1,max+1)` loader.
- All migration numbers are unique; both tenant-list functions have independent grants. New migrations require owner/reviewer allocation before PR creation to prevent namespace reuse.

## Evidence and remaining gates

The refreshed merge job `Staging refresh from pinned latest main and domain migration normalization` passed **397 backend/PostgreSQL tests**, frontend unit tests and TypeScript/Vite production build on the integrated tree, then persisted commit `89fbab34ea8ca70092ae2af5fce96eeaf469ce28`.

The final Chromium/API/Compose checks must also complete successfully **on a commit descendant of the refreshed integration** before a staging pilot can be considered. Green synthetic CI is not a real provider, independent pentest or production release approval.

Remaining release blockers: real tenant-owned IdP registration/MFA consent; trusted HTTPS hostname/proxy; independent permission audit; actual staged backup + restore; rate limits, alerting and SLOs; review of all outstanding PR dependencies and a tested release rollback. The `main` branch can continue moving; always refresh the baseline/CI evidence and resolve any new migration collisions before proposed upstream integration. Never force-push or automatically merge the original PR chain into `main`.
