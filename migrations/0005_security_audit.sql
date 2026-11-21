-- Immutable tenant-bound security audit, inserts only through verified session.
BEGIN;
CREATE TABLE IF NOT EXISTS sme.security_audit (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES sme.tenants(id),
 actor_id uuid NOT NULL REFERENCES sme.identities(id),
 action text NOT NULL CHECK(action IN ('asset.list','session.logout')),
 target_type text NOT NULL CHECK(target_type IN ('asset','session')),
 correlation_id uuid NOT NULL,
 occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_security_audit_tenant_time
 ON sme.security_audit (tenant_id,occurred_at DESC);
REVOKE ALL ON sme.security_audit FROM PUBLIC,sme_app,sme_auth;
ALTER TABLE sme.security_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE sme.security_audit FORCE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION sme.record_session_audit(
 p_session_digest bytea,p_tenant uuid,p_action text,p_target text,p_correlation uuid
) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,sme AS $$
DECLARE actor uuid;
BEGIN
 IF p_session_digest IS NULL OR octet_length(p_session_digest)<>32 OR
    p_correlation IS NULL OR p_action NOT IN ('asset.list','session.logout')
    OR p_target NOT IN ('asset','session') OR
    (p_action='asset.list' AND p_target<>'asset') OR
    (p_action='session.logout' AND p_target<>'session') THEN
   RETURN false;
 END IF;
 SELECT sme.resolve_session(p_session_digest,p_tenant) INTO actor;
 IF actor IS NULL THEN RETURN false; END IF;
 INSERT INTO sme.security_audit(tenant_id,actor_id,action,target_type,correlation_id)
 VALUES(p_tenant,actor,p_action,p_target,p_correlation);
 RETURN true;
END $$;
REVOKE ALL ON FUNCTION sme.record_session_audit(bytea,uuid,text,text,uuid) FROM PUBLIC,sme_auth;
GRANT EXECUTE ON FUNCTION sme.record_session_audit(bytea,uuid,text,text,uuid) TO sme_app;
COMMIT;
