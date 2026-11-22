# M2.12 — PostgreSQL lease primitive

The new SQL functions `sme.try_acquire_asahi_poll` and
`sme.complete_asahi_poll` restrict polling to one current worker for a
server-owned enrolled device. A failed process can be recovered when its lease
expires; next-due time is stored in PostgreSQL so it survives restarts.

The caller must use the restricted ingest role, enrollment credential digest
and a nonzero random worker UUID. Lease holder tokens are not a substitute
for credential authentication. Time is calculated with database `now()`,
never untrusted agent timestamps.

The worker's main loop is **not connected to these functions yet**. Release
remains blocked on operator-approved real device enrollment, durable retry
attempt limits, credential rotation and physical agent testing.
