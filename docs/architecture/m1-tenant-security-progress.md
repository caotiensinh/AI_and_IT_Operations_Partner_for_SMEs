# M1 Tenant Security Foundation — in progress

## Implemented in this change
- PostgreSQL 15+ baseline schema for tenant, identity, membership, site and asset.
- Explicit composite same-tenant foreign key between assets and sites.
- Non-owner application role sme_app without BYPASSRLS.
- FORCE ROW LEVEL SECURITY with deny-by-default policies on memberships/sites/assets.
- Tenant scope via transaction-local sme.tenant_id, never from unauthenticated request headers.
- Pure Python authorization of already-verified identities against active memberships.
- CI workflow targeting real PostgreSQL 16 and six database isolation cases.

## Test evidence and limitations
Five tenant authorization unit tests passed locally; PostgreSQL tests skipped locally because PostgreSQL and psycopg are unavailable there. CI results must be inspected separately. This migration is NOT production readiness.

## Required next
1. OIDC token verification and authenticated membership repository; never instantiate VerifiedIdentity from raw request JSON.
2. Trusted middleware establishes transaction-local tenant context after membership verification.
3. Add tenant RBAC, scoped department/site policies and immutable audit logging.
4. Run migration with non-superuser owner; use separate provisioning credentials and restrict runtime DB grants.
5. Add integration tests for app connection pooling, malformed context, SQL injection, suspended tenants, role escalation and access revocation.
6. Test backups, restores and rollback before pilot data.
