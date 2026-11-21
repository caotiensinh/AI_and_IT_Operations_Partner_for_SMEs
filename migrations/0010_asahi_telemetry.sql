-- Asahi read-only metrics storage. Writes are owned by a FUTURE trusted ingest service.
-- Do not grant public/API/edge agents INSERT on this table.
BEGIN;
CREATE UNIQUE INDEX IF NOT EXISTS uq_assets_tenant_id_site
 ON sme.assets(tenant_id,id,site_id);
CREATE TABLE IF NOT EXISTS sme.asahi_samples (
 tenant_id uuid NOT NULL,
 device_id uuid NOT NULL,
 site_id uuid NOT NULL,
 sampled_at timestamptz NOT NULL,
 received_at timestamptz NOT NULL DEFAULT now(),
 hostname text NOT NULL CHECK (length(hostname) BETWEEN 1 AND 128),
 cpu_percent numeric(5,2) CHECK(cpu_percent BETWEEN 0 AND 100),
 memory_percent numeric(5,2) CHECK(memory_percent BETWEEN 0 AND 100),
 uptime_seconds bigint CHECK(uptime_seconds >= 0),
 PRIMARY KEY(tenant_id,device_id,sampled_at),
 FOREIGN KEY(tenant_id,device_id,site_id)
   REFERENCES sme.assets(tenant_id,id,site_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_asahi_recent
 ON sme.asahi_samples(tenant_id,sampled_at DESC);
REVOKE ALL ON sme.asahi_samples FROM PUBLIC;
ALTER TABLE sme.asahi_samples ENABLE ROW LEVEL SECURITY;
ALTER TABLE sme.asahi_samples FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS asahi_tenant_read ON sme.asahi_samples;
CREATE POLICY asahi_tenant_read ON sme.asahi_samples
 FOR SELECT TO sme_app USING (tenant_id=sme.current_tenant());
REVOKE ALL ON sme.asahi_samples FROM sme_app;
GRANT SELECT ON sme.asahi_samples TO sme_app;
COMMIT;
