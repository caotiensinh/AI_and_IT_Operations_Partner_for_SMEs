# M2.13 — Single leased worker tick

The `run_leased_ingest_tick` function joins the Postgres polling lease
functions with the existing credential-bound Asahi worker. One synchronous
invocation tries to claim the enrollment's current lease, polls only if
the lease was acquired, then sets `next_due`. A retry interval is persisted
on failures. A failed completion after ingest raises rather than reporting
success.

It does not run a daemon or accept arbitrary browser-supplied URLs/tokens.
The function does not configure any real device or send notifications.

**Operational limitations:** lease TTL must exceed worst-case poll+database
time; no extension/heartbeat exists. A worker whose lease expires mid-request
could finish the ingest yet be unable to complete the lease; sample idempotency
and outbox uniqueness avoid duplicate data. Production must add distributed
retry caps, monitoring, correlation IDs, operator-held credential rotation and
observability before connecting to real agents.
