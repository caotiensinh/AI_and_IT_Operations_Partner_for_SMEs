# Case creation idempotency (Spec 003 / BN-003)

## API contract
`POST /v1/tenants/{tenant_id}/research-cases` now REQUIRES an `Idempotency-Key` header containing 16–128 ASCII letters, digits, `_` or `-`. Generate a fresh unpredictable key for each *logical* create operation, persist it client-side until the response has been reconciled, and reuse exactly that key on retry. Do not reuse across different intents. Do not treat keys as an authorization credential.

- First successful creation: `201`, `replayed: false`, persisted `case_id`.
- Identical retry by the same authenticated actor in the same tenant: `200`, `replayed: true`, SAME `case_id`.
- Same key with different normalized label, site or company code: `409` without mutation.
- Missing/invalid key: `422`. Unauthorized session/role/site: `401` or `403`.
- Keys are scoped by VERIFIED actor UUID + tenant UUID; client-provided tenant never grants permission.

## Database invariants
Migration `0007_discovery_idempotency.sql` adds `sme.discovery_create_requests` with unique `(tenant_id, actor_identity_id, request_key)`. A new SECURITY DEFINER function authenticates and rechecks current permission on every request BEFORE accessing existing reservations. A unique-key INSERT with `ON CONFLICT DO NOTHING` serializes concurrent same-key transactions. If reserved before case creation, a DEFERRABLE foreign key keeps reservation/case/event in one atomic transaction; failure rolls all three back.

Existing non-idempotent `sme.create_discovery_case` remains in schema for migration compatibility but `sme_app` can no longer EXECUTE it. `sme_app` has no direct write access to cases, idempotency rows or audit rows.

## Known boundaries and next gates
- No client-facing browser security (cookie/CSRF, throttling, OIDC callback), no update/delete or requirements write API; do not deploy to customers.
- No expiration or pruning of idempotency keys yet. Define retention contract, safe garbage collection and replay-window guarantees before live launch.
- Same idempotency key from different users intentionally refers to different logical operations. A manager must re-authorize on every replay.
- UUID case pagination is not a transactional snapshot under concurrent changes.
- Test with real PostgreSQL 16, including repeated identical payload, conflicting payload, concurrent first-time requests, and direct function privilege denial.

See `docs/architecture/discovery-write-api.md` for prior constraints.