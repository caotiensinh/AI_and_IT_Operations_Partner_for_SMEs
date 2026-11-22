-- Spec 017: verified-session owner-only approval/revocation API.
-- Never grant runtime table writes; execute only via SECURITY DEFINER functions.
BEGIN;
CREATE OR REPLACE FUNCTION sme.approve_asahi_delivery(
 p_digest bytea,p_tenant uuid,p_channel text,
 p_destination_ref text,p_secret_ref text
) RETURNS boolean LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,sme AS $$
DECLARE actor uuid;
BEGIN
 IF p_digest IS NULL OR octet_length(p_digest)<>32
    OR p_tenant IS NULL
    OR p_channel IS NULL OR p_channel NOT IN ('email','webhook')
    OR p_destination_ref IS NULL OR p_secret_ref IS NULL
    OR length(p_destination_ref) NOT BETWEEN 1 AND 128
    OR length(p_secret_ref) NOT BETWEEN 1 AND 128
    OR p_destination_ref !~ '^[A-Za-z0-9_./-]{1,128}$'
    OR p_secret_ref !~ '^[A-Za-z0-9_./-]{1,128}$'
    OR p_destination_ref ~ '(^|/)[.][.](/|$)'
    OR p_secret_ref ~ '(^|/)[.][.](/|$)'
    OR left(p_destination_ref,1)='/' OR left(p_secret_ref,1)='/'
 THEN RETURN false; END IF;
 SELECT sme.resolve_session(p_digest,p_tenant) INTO actor;
 IF actor IS NULL OR NOT EXISTS (
  SELECT 1 FROM sme.role_assignments r
  WHERE r.tenant_id=p_tenant AND r.identity_id=actor
    AND r.role='owner' AND r.scope_type='tenant'
 ) THEN RETURN false; END IF;
 INSERT INTO sme.asahi_delivery_destinations (
  tenant_id,channel,destination_ref,secret_ref,enabled,
  approved_by,approved_at,revoked_at
 ) VALUES (
  p_tenant,p_channel,p_destination_ref,p_secret_ref,true,
  actor,now(),NULL
 )
 ON CONFLICT (tenant_id) DO UPDATE
  SET channel=EXCLUDED.channel,
      destination_ref=EXCLUDED.destination_ref,
      secret_ref=EXCLUDED.secret_ref,
      enabled=true,approved_by=EXCLUDED.approved_by,
      approved_at=now(),revoked_at=NULL;
 RETURN true;
END $$;

CREATE OR REPLACE FUNCTION sme.revoke_asahi_delivery(
 p_digest bytea,p_tenant uuid
) RETURNS boolean LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,sme AS $$
DECLARE actor uuid; modified integer;
BEGIN
 IF p_digest IS NULL OR octet_length(p_digest)<>32 OR p_tenant IS NULL
 THEN RETURN false; END IF;
 SELECT sme.resolve_session(p_digest,p_tenant) INTO actor;
 IF actor IS NULL OR NOT EXISTS (
  SELECT 1 FROM sme.role_assignments r
  WHERE r.tenant_id=p_tenant AND r.identity_id=actor
    AND r.role='owner' AND r.scope_type='tenant'
 ) THEN RETURN false; END IF;
 UPDATE sme.asahi_delivery_destinations
 SET enabled=false,revoked_at=now(),approved_by=actor
 WHERE tenant_id=p_tenant AND enabled=true AND revoked_at IS NULL;
 GET DIAGNOSTICS modified=ROW_COUNT;
 RETURN modified=1;
END $$;
REVOKE ALL ON FUNCTION sme.approve_asahi_delivery(bytea,uuid,text,text,text)
 FROM PUBLIC,sme_auth,sme_ingest,sme_dispatch;
REVOKE ALL ON FUNCTION sme.revoke_asahi_delivery(bytea,uuid)
 FROM PUBLIC,sme_auth,sme_ingest,sme_dispatch;
GRANT EXECUTE ON FUNCTION sme.approve_asahi_delivery(bytea,uuid,text,text,text) TO sme_app;
GRANT EXECUTE ON FUNCTION sme.revoke_asahi_delivery(bytea,uuid) TO sme_app;
-- Correct the Spec 016 BEFORE INSERT audit duplication under INSERT ON CONFLICT.
-- Audit only the final physical operation. Keep safety checks BEFORE mutations.
DROP TRIGGER IF EXISTS trg_asahi_delivery_policy_audit ON sme.asahi_delivery_destinations;
DROP TRIGGER IF EXISTS trg_asahi_delivery_policy_guard ON sme.asahi_delivery_destinations;
CREATE OR REPLACE FUNCTION sme.guard_asahi_delivery_policy()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,sme AS $body$
BEGIN
 IF TG_OP='DELETE' THEN
  RAISE EXCEPTION 'delivery policies must be revoked, not deleted';
 END IF;
 IF TG_OP='UPDATE' AND NEW.tenant_id<>OLD.tenant_id THEN
  RAISE EXCEPTION 'cannot move policy between tenants';
 END IF;
 RETURN NEW;
END $body$;
CREATE OR REPLACE FUNCTION sme.record_asahi_delivery_policy_audit()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,sme AS $body$
BEGIN
 INSERT INTO sme.asahi_delivery_policy_audit(
  tenant_id,actor_id,operation,previous_enabled,current_enabled
 ) VALUES(
  NEW.tenant_id,NEW.approved_by,
  CASE WHEN TG_OP='INSERT' THEN 'created'
       WHEN NEW.revoked_at IS NOT NULL AND OLD.revoked_at IS NULL THEN 'revoked'
       ELSE 'updated' END,
  CASE WHEN TG_OP='INSERT' THEN NULL ELSE OLD.enabled END,
  NEW.enabled
 );
 RETURN NEW;
END $body$;
REVOKE ALL ON FUNCTION sme.guard_asahi_delivery_policy() FROM PUBLIC;
REVOKE ALL ON FUNCTION sme.record_asahi_delivery_policy_audit() FROM PUBLIC;
CREATE TRIGGER trg_asahi_delivery_policy_guard
 BEFORE UPDATE OR DELETE ON sme.asahi_delivery_destinations
 FOR EACH ROW EXECUTE FUNCTION sme.guard_asahi_delivery_policy();
CREATE TRIGGER trg_asahi_delivery_policy_audit
 AFTER INSERT OR UPDATE ON sme.asahi_delivery_destinations
 FOR EACH ROW EXECUTE FUNCTION sme.record_asahi_delivery_policy_audit();

COMMIT;
