# Spec 016 — PostgreSQL tenant alert delivery approvals

## Goal
Persist per-tenant **opaque** delivery references and an append-only approval change log, and expose configuration to the restricted dispatcher **only while a live event lease is held**.

## L1 / L2 / L3 boundary
- L1: enterprise owner approval UI **not implemented**; owner identity approval workflow remains a blocker.
- L2: policy verifier requires claimed durable event ID and lease owner; it does not trust a client-supplied tenant.
- L3: migration-owner-provisioned PostgreSQL policy table, audit trigger and strictly granted SECURITY DEFINER resolver. No actual URL or password is stored in the policy.

## Acceptance
- [x] No destination row or disabled/revoked destination denies lookup.
- [x] Only a current lease owner of a not-yet-delivered event can resolve references; suspended tenants deny.
- [x] Runtime application/auth/ingest cannot invoke resolver; all runtime roles are denied direct table reads.
- [x] Audit rows for creation, changes and revocation; prevent deleting a policy row.
- [x] Strict opaque reference syntax and fail-closed default.
- [ ] CI integration tests PASS on disposable PostgreSQL before merge.
- [ ] Authorized owner step-up approval, current membership/role verification, signed audit, secure changes and revocation.
- [ ] External secret manager, egress validation, webhook SSRF defense, agent telemetry and real notifier provider.
- [ ] Production security review, monitor/rollback and physical Asahi E2E.

## Explicit limitations
Migration-owner-only provisioning is a temporary trust boundary, not customer-facing approvals. This change **does not establish that any real person authorized a destination**. Audit table is append-only to runtime roles but an unrestricted migration owner can modify its data; immutable/WORM exports are future work. At-least-once provider delivery requires idempotency; not exactly-once.
