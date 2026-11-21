# M1.7 — Tenant session audit foundation

## Delivered
- Dedicated append-only-by-grants audit table, no runtime SELECT/UPDATE/DELETE permissions.
- Successful protected asset reads record tenant_id, authenticated actor, action, resource category, correlation UUID, timestamp within the same transaction.
- Narrow SECURITY DEFINER recording function derives actor from valid session + selected active tenant; caller cannot supply arbitrary actor.
- Denied cross-tenant recording, mutation and valid audit insertion tested on PostgreSQL.

## Known gaps before pilot
- Audit for rejected login attempts, logout, role/membership changes, exports, support grants, requests and global platform operations.
- Audit log shipping to tamper-evident remote sink, lifecycle/retention/legal hold and monitoring.
- Real distributed trace ID, structured logging and operational alerting.
- Production credential and key rotation; browser assets API and live OIDC authentication.
- Existing audit only proves SQL write restrictions, not superuser/physical tamper resistance.

M1.7 is an incremental audit foundation, not a compliance certification.
