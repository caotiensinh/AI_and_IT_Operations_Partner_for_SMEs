# Real database-login smoke for ingest runtime

A staging-only CI script runs through a disposable PostgreSQL client container
on the private Compose network, authenticates as **sme_ingest_runtime** using
the generated password and verifies permission to `SET ROLE sme_ingest`.
It independently tests failed `SET ROLE sme_app` and `SET ROLE sme_auth`
attempts and denial of direct enrollment credential reads.

The test does not expose the database port. Secrets are not printed.
The Docker container used for the check is temporary; it is not a polling
worker and does not connect to a real device.

## Remaining
- Secret manager and rotation, per-device enrollment approval, durable
  scheduler, real hardware TLS identity checks and operational alerts
- Non-privileged dedicated worker image with dynamic agent enrollment lookup
- A real hardware E2E across two isolated tenants
