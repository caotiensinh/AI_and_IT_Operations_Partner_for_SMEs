# Research discovery PostgreSQL read-only slice — M3 prototype

Status: code + migrations committed; **not a production or customer intake service**.

## Migration and transaction boundaries
Migration `0005_discovery_read_model.sql` requires foundation `0001`, scoped roles `0002`, and sessions `0003`. Run with a dedicated migration owner, never the runtime DB identity. The migration creates scoped cases, source references (metadata only; no PDF bytes) and requirement rows, all with composite tenant foreign keys and forced RLS. All three tables are **SELECT-only** for `sme_app`. No application permission to insert/update/delete and no public schema grants.

Read API: `GET /v1/tenants/{tenant_id}/research-cases`. It uses the existing opaque session hash, resolves active tenant membership server-side, sets the RLS context in the same transaction, reads trusted role assignments and filters resources through RBAC. Site-scope and tenant-scope grants are supported. Department-only grants will see no cases because a research case is site-bound until department scope exists. Exposes case ID/site ID, label, company-code and status; does not expose confidential source text or documents. Returns no more than 101 cases and is **not a complete pagination contract**.

## Threat model and explicit constraints
- A client-supplied tenant_id alone is not authority; active session and membership are checked.
- A role-less valid member sees an empty list, not other tenants.
- Invalid, forged and missing sessions fail.
- Production-ready login callback, secure cookies/CSRF, robust pagination, case creation/update approvals, immutable audit, attachment access and consent checks remain **OPEN**.
- Test seeds use invented labels; never persist private source PDFs or customer data in this codebase.
- The in-memory `business_discovery.py` policy model is *advisory* and cannot substitute for DB constraints or API authentication.
- For production, additionally prove restricted database ownership/connection pooling boundaries and field-level confidentiality.

## Verification
`SME_TEST_DATABASE_DSN` must point to a disposable PostgreSQL database. The existing `.github/workflows/tenant-rls.yml` uses PostgreSQL 16 and executes the full Python unittest suite. `tests/test_discovery_postgres.py` includes cross-tenant, missing-context, forged-token, revoked-role, read-only grants, cross-case source integrity, false confirmed inference and explicit-source requirements.

## Next steps
1. Add bounded, cursor-based pagination with RBAC-aware filtering.
2. Add permission/consent checked import paths and immutable audit events, distinct from runtime read-only role.
3. Implement approved create/update API under a least-privilege role with tests for site/department scoping and concurrent writes.
4. Build Japanese-first research workflow UI and downloadable sanitized decision pack.
5. Obtain customer consent and measure actual process baselines before claiming pilot readiness.
