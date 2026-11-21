-- M2.5: server-owned enrollment and restricted, credential-bound ingestion.
-- No browser/ordinary runtime account may enroll or write telemetry.
BEGIN;
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sme_ingest') THEN
  CREATE ROLE sme_ingest NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
 END IF;
END $$;
GRANT USAGE ON SCHEMA sme TO sme_ingest;
CREATE TABLE IF NOT EXISTS sme.asahi_enrollments (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 site_id uuid NOT NULL,
 device_id uuid NOT NULL,
 credential_digest bytea NOT NULL CHECK (octet_length(credential_digest)=32),
 status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','revoked')),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id, device_id),
 FOREIGN KEY (tenant_id,device_id,site_id)
   REFERENCES sme.assets(tenant_id,id,site_id) ON DELETE RESTRICT
);
REVOKE ALL ON sme.asahi_enrollments FROM PUBLIC,sme_app,sme_ingest;
-- The table owner is a separately privileged enrollment operator.
-- Avoid access to the sensitive digest from ingestion/application roles.

-- FORCE RLS remains in effect on sample storage. The ingest function sets
-- a transaction-local tenant only AFTER verifying an enrollment credential.
DROP POLICY IF EXISTS asahi_verified_insert ON sme.asahi_samples;
CREATE POLICY asahi_verified_insert ON sme.asahi_samples
 FOR INSERT TO PUBLIC WITH CHECK (tenant_id=sme.current_tenant());
CREATE OR REPLACE FUNCTION sme.ingest_asahi_sample(
 p_enrollment uuid, p_credential_digest bytea, p_sampled_at timestamptz,
 p_hostname text, p_cpu numeric, p_memory numeric, p_uptime bigint
) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,sme AS $$
DECLARE e record;
DECLARE inserted uuid;
BEGIN
 IF p_enrollment IS NULL OR p_credential_digest IS NULL
    OR octet_length(p_credential_digest)<>32 OR p_sampled_at IS NULL
    OR p_sampled_at < now()-interval '5 minutes'
    OR p_sampled_at > now()+interval '5 minutes'
    OR p_hostname IS NULL OR length(p_hostname) NOT BETWEEN 1 AND 128
    OR p_hostname ~ '[[:cntrl:]]'
    OR (p_cpu IS NOT NULL AND (p_cpu<0 OR p_cpu>100))
    OR (p_memory IS NOT NULL AND (p_memory<0 OR p_memory>100))
    OR (p_uptime IS NOT NULL AND p_uptime<0)
 THEN RETURN false; END IF;
 SELECT en.id,en.tenant_id,en.site_id,en.device_id INTO e
 FROM sme.asahi_enrollments en
 JOIN sme.tenants t ON t.id=en.tenant_id AND t.status='active'
 WHERE en.id=p_enrollment AND en.status='active'
   AND en.credential_digest=p_credential_digest;
 IF NOT FOUND THEN RETURN false; END IF;
 PERFORM set_config('sme.tenant_id',e.tenant_id::text,true);
 INSERT INTO sme.asahi_samples(
    tenant_id,device_id,site_id,sampled_at,hostname,
    cpu_percent,memory_percent,uptime_seconds
 ) VALUES (
    e.tenant_id,e.device_id,e.site_id,p_sampled_at,p_hostname,
    p_cpu,p_memory,p_uptime
 ) ON CONFLICT (tenant_id,device_id,sampled_at) DO NOTHING
 RETURNING device_id INTO inserted;
 RETURN inserted IS NOT NULL;
END $$;
REVOKE ALL ON FUNCTION sme.ingest_asahi_sample(uuid,bytea,timestamptz,text,numeric,numeric,bigint)
 FROM PUBLIC,sme_app,sme_auth;
GRANT EXECUTE ON FUNCTION sme.ingest_asahi_sample(uuid,bytea,timestamptz,text,numeric,numeric,bigint)
 TO sme_ingest;
COMMIT;
