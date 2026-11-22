# Spec 010 — Atomic telemetry to outbox

- [x] Integrate existing restricted ingest worker with database evaluator
- [x] Keep insert + alert state + outbox inside one transaction
- [x] Add double-high-sample E2E test and duplicate replay assertion
- [x] Add forced evaluator-failure rollback regression test
- [ ] Verify CI on PostgreSQL, Chromium and staging
- [ ] Merge when all CI gates PASS
- [ ] Introduce durable worker scheduling and outbox delivery separately
