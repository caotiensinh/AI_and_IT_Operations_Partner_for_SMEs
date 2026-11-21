-- Expand the closed audit vocabulary for read-only Asahi telemetry.
BEGIN;
ALTER TABLE sme.security_audit
 DROP CONSTRAINT IF EXISTS security_audit_action_check;
ALTER TABLE sme.security_audit
 ADD CONSTRAINT security_audit_action_check
 CHECK (action IN ('asset.list','session.logout','telemetry.read'));
ALTER TABLE sme.security_audit
 DROP CONSTRAINT IF EXISTS security_audit_target_type_check;
ALTER TABLE sme.security_audit
 ADD CONSTRAINT security_audit_target_type_check
 CHECK (target_type IN ('asset','session','telemetry'));
CREATE OR REPLACE FUNCTION sme.record_session_audit(
 p_session_digest bytea,p_tenant uuid,p_action text,p_target text,p_correlation uuid
) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,sme AS $$
DECLARE actor uuid;
BEGIN
 IF p_session_digest IS NULL OR octet_length(p_session_digest)<>32
    OR p_correlation IS NULL OR NOT (
      (p_action='asset.list' AND p_target='asset')
      OR (p_action='session.logout' AND p_target='session')
      OR (p_action='telemetry.read' AND p_target='telemetry')
    ) THEN
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
