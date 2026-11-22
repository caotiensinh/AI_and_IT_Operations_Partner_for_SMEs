# Spec 013 — Alert outbox dispatch claim/ack, retry and dead-letter

## Goal
Provide durable **at-least-once** delivery bookkeeping for Asahi alert outbox
messages. No customer-facing delivery channel is activated in this change.

## Acceptance
- Separate `sme_dispatch` NOLOGIN role can execute only claim/finish functions.
- Claim is one-row atomic `FOR UPDATE SKIP LOCKED` and protects against
  concurrent dispatch workers; only active tenants are eligible.
- Claim returns event id, tenant/site/device and metric transition; it never
  accepts an external delivery address.
- Lease 5–300 s, retry 5–3600 s, at most five recorded attempts.
- Wrong owner or expired lease cannot mark a message delivered.
- A confirmed provider success is required to set `delivered_at`.
- A failed attempt is delayed; after five attempts it is dead-lettered.
- Read/write access to queue table denied to app/ingest/dispatch roles.
- PostgreSQL integration tests validate concurrent claim, wrong owner,
  retry, dead-letter, inactive tenant and permission denial.
- All existing integration and browser/staging checks remain green.

## Limits
At-least-once means a provider could receive a duplicate if sending succeeds
but the acknowledgement fails or its lease expires. A future delivery adapter
MUST pass a stable event_id idempotency key where supported, and must resolve
per-tenant approved destination/credentials from server-side policy. This
migration does **not** provide exactly-once external delivery, a destination
policy, notifier credentials, external network calls, or a daemon.
