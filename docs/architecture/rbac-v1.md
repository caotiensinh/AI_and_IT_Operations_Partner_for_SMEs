# M1.2 — RBAC and organization hierarchy baseline

## Verified scope
- Role templates: owner, admin, manager, operator and viewer.
- Permissions: resource.read/update, alert.acknowledge, workflow.approve, users.manage, tenant.configure.
- Explicit grants at tenant, site or department level; department ancestor inheritance is **only** accepted from a trusted tenant-scoped recursive query.
- SQL enforces same-tenant membership and department/site relations; role assignments cannot be written via the runtime app role.
- PostgreSQL RLS also protects department and assignment reads.

## Trust boundary and release restrictions
**Not an authentication system.** The Python decision function accepts already verified context, assignments and resources. All three must come from trusted server-controlled sources, never browser JSON, tenant headers, unsigned JWT claims or LLM output.

Database RLS currently enforces tenant boundaries only. Department access is enforced by Python logic once the future API is implemented; raw app database credentials would bypass department authorization. Do not expose app database credentials to end users, edge workers, or tenant administrators.

The current `sme_app` can change transaction-local `sme.tenant_id`; only the trusted API may own these DB credentials. Provisioning/role mutation must be moved to an audited elevated service with step-up MFA, approval and tests. OIDC token verification, membership lookup, API E2E, per-department SQL policy, support grants, immutable audit and account recovery are still open.

## Required next
1. Implement OIDC issuer/audience/signature verification, rotating JWKS and short-lived sessions.
2. Database-backed memberships, explicit tenant switch and roles from DB; do not accept role assertions from clients.
3. Add an audit/outbox transactional record and authenticated API integration tests.
4. Refine database protection per department where necessary; test pooled connections under concurrent tenants.
5. Apply credential separation for migration, provisioning and runtime and review SQL grants.
