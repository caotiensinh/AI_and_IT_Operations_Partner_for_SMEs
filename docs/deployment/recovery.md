# Disposable staging backup + restore drill (not production recovery)

The CI test creates one synthetic tenant in the staging PostgreSQL database,
exports a PostgreSQL custom-format dump and imports it to a separate `sme_restore`
database. It proves that this one SQL row and the FORCE RLS flags on the three
core scoped tables survive a basic restore. The test runs only under
`SME_E2E_FIXTURE_MODE=disposable_ci_only`; it must never touch real customer data.

## Production backup requirements still OPEN
- Coordinated point-in-time recovery, WAL archiving and incremental backups.
- Encryption, retention, independent backup location and credential separation.
- Per-tenant export/delete and object store versioning.
- Enforced, measured RPO/RTO and automated recovery exercise with alerting.
- Application and audit consistency, key management, operational runbooks.
