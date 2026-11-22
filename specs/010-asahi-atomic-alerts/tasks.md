# Spec 010 — Atomic telemetry to outbox

- [x] Integrate existing restricted ingest worker with database evaluator
- [x] Keep insert + alert state + outbox inside one transaction
- [x] Add double-high-sample E2E test and duplicate replay assertion
- [x] Add forced evaluator-failure rollback regression test
- [x] Verify 218/218 Python/PostgreSQL and five PR #42 CI workflows PASS
- [x] Merge PR #42 after verifying required CI checks
- [ ] Introduce durable worker scheduling and outbox delivery separately
