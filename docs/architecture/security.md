# Multi-Tenant Security, Identity and Authorization

## Threat boundaries
Tenant A must never read, mutate, infer, export or influence Tenant B data. UI filtering is insufficient. Enforce in API, database, object storage, async workers, cache, vector search, telemetry, backups and support tools.

## Entity model
User(identity_id) — Membership(tenant_id, user_id, status) — RoleAssignment(membership_id, role, scope_type, scope_id) — Resource(tenant_id, site_id, department_id, ...).
Tenant has sites, departments, groups, licensed modules, retention policies, encryption key references and audit policy.
Service principals are distinct from human identities. No shared super-admin credential.

## Role matrix (default templates; custom policies later)
| Permission | Platform admin | Tenant owner | Tenant admin | Manager | Operator | Viewer |
|---|---|---|---|---|---|---|
| Platform billing/config | Yes | No | No | No | No | No |
| Customer business payload | No* | Scoped all | Scoped all | Department | Assigned | Read assigned |
| Invite users | No* | Yes | Yes | No by default | No | No |
| Assign tenant owner | No* | Yes with MFA | No | No | No | No |
| Configure tenant integrations | No* | Yes | Yes | No | No | No |
| Execute operational actions | No* | Policy | Policy | Scoped | Scoped | No |
| Read tenant audit | Metadata only | Yes | Yes | Scoped | No | Scoped audit |
*Requires explicit tenant-approved, expiring, audited support grant for any customer-data access.

## PostgreSQL RLS
- Every tenant-owned row has non-null tenant_id. FK references should enforce same-tenant relationships using composite keys where suitable.
- Database application role must not own tenant tables, have BYPASSRLS or table-owner privilege; use FORCE ROW LEVEL SECURITY.
- Transaction middleware sets tenant context using parameterized SET LOCAL/config via set_config inside the same transaction, with connection pooling tested.
- Policy defaults to deny when tenant context missing. Match tenant_id to current_setting('app.tenant_id', true) cast safely through an approved database helper.
- Separate migration owner and application DB roles; never use a superuser for requests.
- All direct SQL and out-of-band workers must meet equivalent tenant validation.

## API authorization
1. Validate OIDC session, issuer, audience and token age.
2. Select tenant only from memberships authenticated server-side.
3. Resolve action → permission → scope → resource tenant.
4. Apply data access constraints and RLS, then audit decisions for privileged operations.
5. Do not trust X-Tenant-ID alone; avoid insecure direct object references.

## File and background isolation
- Prefix objects with opaque tenant UUID; use server-brokered short-lived signed URLs and object-level authorization.
- Encryption, retention, export/delete and backups are tenant-aware.
- Async queue messages contain tenant context but worker validates membership/service principal, capabilities and tenant-scoped resources again.
- Cache keys and search indexes include tenant namespace; never pool sensitive AI retrieval results across tenants.
- Every external model use requires policy, purpose, retention and redaction checks.

## Security test matrix
- Tenant A token accesses B ID, B list, B file, B export, B queue result: DENY.
- Same identity has memberships A/B: explicit switch; no context bleed under pooled connections.
- Expired support grant: DENY; grant/revoke appears in audit.
- Viewer attempts write or owner elevation: DENY.
- Missing tenant context on SQL connection: zero visible records / DENY.
- Stale presigned URL and unauthorized object lookup: DENY after expiry; revoke requires policy/credential measures beyond expiry.
- Device from site A tries to send data to site B: DENY.
