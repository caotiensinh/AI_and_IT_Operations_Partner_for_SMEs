# Implementation plan — Spec 004

Dependency graph:
1. Confirm Asahi source schema and existing security primitives (done).
2. Add PostgreSQL metrics schema + role grants + composite FK (done).
3. Add latest-samples API using session, RBAC and RLS (done).
4. Add React Monitoring view and disabled/empty states (done).
5. Add database negative tests and Chromium data-isolation checks (committed;
   CI acceptance pending).
6. Inspect CI and fix root causes; merge only after all required lanes PASS.
7. Next standalone feature: trusted enrollment and ingest adapter with
   independent identity/credential and replay-protection threat model.

Rollback: revert feature commit/PR while preserving additive migration; deleting
the telemetry table is NOT an automated rollback because it would lose data.
Runtime clients cannot write this table.
