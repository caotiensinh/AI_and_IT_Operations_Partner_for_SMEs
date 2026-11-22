# M2.11 — Transactional Asahi ingest → alert evaluation

The existing `ingest_one()` now executes `sme.evaluate_asahi_alert`
immediately after a successful `sme.ingest_asahi_sample` call, **inside the
same PostgreSQL transaction**. If evaluation fails, the sample insert rolls
back with it. Duplicate samples do not cause re-evaluation.

Tests use the actual adapter and worker with a mocked remote HTTPS response
and a real PostgreSQL database to verify two successive high CPU observations
produce exactly one outbox transition. A forced database permission failure
verifies atomic rollback.

No real agent, notification delivery, credential provisioning, or long-lived
worker is introduced. Outbox retention and multi-worker delivery remain open.
