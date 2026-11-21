-- Idempotent discovery case creation. Applies after migration 0006.
-- Keys are scoped to a verified actor + tenant, never to a browser-supplied identity.
BEGIN;
CREATE TABLE IF NOT EXISTS sme.discovery_create_requests (
 tenant_id uuid NOT NULL,
 actor_identity_id uuid NOT NULL,
 request_key text NOT NULL CHECK (length(request_key) BETWEEN 16 AND 128),
 case_id uuid NOT NULL,
 site_id uuid NOT NULL,
 label text NOT NULL,
 company_code text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (tenant_id,actor_identity_id,request_key),
 FOREIGN KEY (tenant_id,case_id) REFERENCES sme.discovery_cases(tenant_id,id)
  DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY (actor_identity_id) REFERENCES sme.identities(id)
);
ALTER TABLE sme.discovery_create_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE sme.discovery_create_requests FORCE ROW LEVEL SECURITY;
REVOKE ALL ON sme.discovery_create_requests FROM PUBLIC,sme_app;
GRANT INSERT,SELECT ON sme.discovery_create_requests TO sme_discovery_service;
DROP POLICY IF EXISTS discovery_request_select ON sme.discovery_create_requests;
CREATE POLICY discovery_request_select ON sme.discovery_create_requests
 FOR SELECT TO sme_discovery_service USING (tenant_id=sme.current_tenant());
DROP POLICY IF EXISTS discovery_request_insert ON sme.discovery_create_requests;
CREATE POLICY discovery_request_insert ON sme.discovery_create_requests
 FOR INSERT TO sme_discovery_service WITH CHECK (tenant_id=sme.current_tenant());

CREATE OR REPLACE FUNCTION sme.create_discovery_case_once(
 p_digest bytea,p_tenant uuid,p_site uuid,p_label text,p_company text,p_key text
) RETURNS TABLE(result_case_id uuid,is_replay boolean,is_conflict boolean)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,sme
AS $$
DECLARE
 actor uuid;
 new_id uuid;
 prior record;
 inserted integer;
 normalized_label text;
BEGIN
 IF p_digest IS NULL OR octet_length(p_digest)<>32 OR p_tenant IS NULL
    OR p_site IS NULL OR p_label IS NULL OR p_company IS NULL
    OR p_key IS NULL OR p_key !~ '^[A-Za-z0-9_-]{16,128}$'
    OR length(btrim(p_label)) NOT BETWEEN 1 AND 200
    OR p_company NOT IN ('B','J','L','R','OTHER') THEN
   RETURN;
 END IF;
 normalized_label := btrim(p_label);
 actor := sme.resolve_session(p_digest,p_tenant);
 IF actor IS NULL THEN RETURN; END IF;
 PERFORM set_config('sme.tenant_id',p_tenant::text,true);
 IF NOT EXISTS (SELECT 1 FROM sme.sites WHERE tenant_id=p_tenant AND id=p_site) THEN
   RETURN;
 END IF;
 -- Revalidate current authority on EVERY replay; a stale key is not permission.
 IF NOT EXISTS (
   SELECT 1 FROM sme.role_assignments ra
   WHERE ra.tenant_id=p_tenant AND ra.identity_id=actor
     AND ((ra.role IN ('owner','admin','manager') AND ra.scope_type='tenant')
       OR (ra.role='manager' AND ra.scope_type='site' AND ra.site_id=p_site))
 ) THEN RETURN; END IF;
 new_id := gen_random_uuid();
 -- Atomic reservation: concurrent identical requests wait on unique index resolution.
 -- Deferred FK ensures case + event + key are committed or rolled back together.
 INSERT INTO sme.discovery_create_requests
   (tenant_id,actor_identity_id,request_key,case_id,site_id,label,company_code)
 VALUES (p_tenant,actor,p_key,new_id,p_site,normalized_label,p_company)
 ON CONFLICT (tenant_id,actor_identity_id,request_key) DO NOTHING;
 GET DIAGNOSTICS inserted=ROW_COUNT;
 IF inserted=0 THEN
   SELECT d.case_id,d.site_id,d.label,d.company_code INTO prior
   FROM sme.discovery_create_requests d
   WHERE d.tenant_id=p_tenant AND d.actor_identity_id=actor
     AND d.request_key=p_key;
   IF NOT FOUND THEN RAISE EXCEPTION 'idempotency lookup unavailable'; END IF;
   IF prior.site_id IS DISTINCT FROM p_site OR prior.label IS DISTINCT FROM normalized_label
      OR prior.company_code IS DISTINCT FROM p_company THEN
     RETURN QUERY SELECT prior.case_id,true,true;
     RETURN;
   END IF;
   RETURN QUERY SELECT prior.case_id,true,false;
   RETURN;
 END IF;
 INSERT INTO sme.discovery_cases(tenant_id,id,site_id,label,company_code,status)
 VALUES (p_tenant,new_id,p_site,normalized_label,p_company,'research');
 INSERT INTO sme.discovery_change_events(tenant_id,case_id,actor_identity_id,action)
 VALUES (p_tenant,new_id,actor,'case.created');
 RETURN QUERY SELECT new_id,false,false;
END $$;
ALTER FUNCTION sme.create_discovery_case_once(bytea,uuid,uuid,text,text,text)
 OWNER TO sme_discovery_service;
REVOKE ALL ON FUNCTION sme.create_discovery_case_once(bytea,uuid,uuid,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION sme.create_discovery_case_once(bytea,uuid,uuid,text,text,text) TO sme_app;
-- Disallow the legacy non-idempotent path from the application.
REVOKE EXECUTE ON FUNCTION sme.create_discovery_case(bytea,uuid,uuid,text,text) FROM sme_app;
COMMIT;
