# Spec 013 — Dispatch bookkeeping tasks

- [x] Add separate restricted `sme_dispatch` role and SQL claim/finish
- [x] Implement bounded lease, retry schedule and dead-letter transition
- [x] Use atomic SKIP LOCKED claim for multiple workers
- [ ] Verify real PostgreSQL positive/negative/concurrent tests
- [ ] Verify five workflow gates and merge
- [ ] Add approved per-tenant destination policy and secret-manager integration
- [ ] Build network delivery worker with idempotency keys and operator audit
- [ ] Validate physical Asahi agent and end-to-end customer notification
