# M2.2: Persisted Asahi metrics — read-only tenant slice

## Delivered
- PostgreSQL `sme.asahi_samples` retains CPU, RAM and uptime with a compound
  foreign key to the asset and its actual site within the **same tenant**.
- Per-tenant FORCE RLS; normal application account receives SELECT only.
- Protected read-only latest-samples endpoint uses session membership, RBAC
  **per asset/site**, and a transactional tenant context.
- React UI shows current telemetry rows returned by the authenticated API,
  rather than synthetic metrics.
- PostgreSQL tests cover two tenants, scoped roles, anonymous/revoked access,
  a cross-tenant query, forged site relationship and runtime write denial.

## Not yet implemented (must not mark PASS)
- No live ASAHI agent enrollment, polling, TLS fingerprint validation or
  telemetry ingestion endpoint.
- In CI, the schema owner seeds synthetic samples for read-path verification.
  **This is test data, not a connected device**.
- No alarm engine, retention job, downsampling, time-series chart, dashboards,
  agent status SLO, mTLS enrollment, replay control or metric encryption strategy.
- Do not enable the adapter in production until trusted agent identity and
  a separate least-privilege ingestion service exist.
- Future ingestion worker MUST call `normalize_asahi_snapshot` after resolving
  a server-controlled tenant/site/device binding. It must not receive a
  write-capable DB credential from users, agents or the general web API.
