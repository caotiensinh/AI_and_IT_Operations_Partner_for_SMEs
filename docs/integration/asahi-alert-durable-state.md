# M2.10 — Durable alert decisions, without notification delivery

Migration `0013_asahi_alert_outbox.sql` adds tenant-bound state and a unique,
append-only outbox for CPU/RAM transitions. A restrictive SQL function checks
active enrollment and its credential digest, then reads *persisted* telemetry
samples to prevent caller-selected metric values. Each device/metric row is
locked during evaluation. The result is a count of newly queued events.

The ingest role can execute the function but cannot read the credential
table, state or outbox. The web/auth roles cannot execute it. Test fixtures
run on disposable PostgreSQL only. See Spec 009.

**Not shipped**: alert sending, incident/ack UI, external providers, secret
manager, real agent execution, multi-worker leasing for delivery.
