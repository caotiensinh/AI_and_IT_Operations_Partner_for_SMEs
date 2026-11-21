-- Evidence-aware requirement creation; requires migration 0008.
BEGIN;
GRANT INSERT,SELECT ON sme.discovery_requirements TO sme_discovery_service;
DROP POLICY IF EXISTS discovery_writer_requirement_read ON sme.discovery_requirements;
CREATE POLICY discovery_writer_requirement_read ON sme.discovery_requirements
 FOR SELECT TO sme_discovery_service USING (tenant_id=sme.current_tenant());
DROP POLICY IF EXISTS discovery_writer_requirement_insert ON sme.discovery_requirements;
CREATE POLICY discovery_writer_requirement_insert ON sme.discovery_requirements
 FOR INSERT TO sme_discovery_service WITH CHECK (tenant_id=sme.current_tenant());
ALTER TABLE sme.discovery_change_events DROP CONSTRAINT IF EXISTS discovery_change_events_action_check;
ALTER TABLE sme.discovery_change_events ADD CONSTRAINT discovery_change_events_action_check
 CHECK(action IN ('case.created','source.created','requirement.created'));
CREATE OR REPLACE FUNCTION sme.create_discovery_requirement_once(
 p_digest bytea,p_tenant uuid,p_case uuid,p_req uuid,p_statement text,
 p_classification text,p_source uuid
) RETURNS TABLE(result_requirement_id uuid,is_replay boolean,is_conflict boolean)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,sme
AS $$
DECLARE
 actor uuid;
 site uuid;
 prior record;
 inserted integer;
 normalized_statement text;
BEGIN
 IF p_digest IS NULL OR octet_length(p_digest)<>32
    OR p_tenant IS NULL OR p_case IS NULL OR p_req IS NULL
    OR p_statement IS NULL OR length(btrim(p_statement)) NOT BETWEEN 1 AND 4000
    OR p_classification IS NULL
    OR p_classification NOT IN ('explicit','inferred','unverified')
    OR (p_classification='explicit' AND p_source IS NULL) THEN RETURN; END IF;
 normalized_statement:=btrim(p_statement);
 actor:=sme.resolve_session(p_digest,p_tenant);
 IF actor IS NULL THEN RETURN; END IF;
 PERFORM set_config('sme.tenant_id',p_tenant::text,true);
 SELECT c.site_id INTO site FROM sme.discovery_cases c
 WHERE c.tenant_id=p_tenant AND c.id=p_case AND c.status='research';
 IF NOT FOUND THEN RETURN; END IF;
 IF NOT EXISTS (
  SELECT 1 FROM sme.role_assignments r
  WHERE r.tenant_id=p_tenant AND r.identity_id=actor
   AND ((r.role IN ('owner','admin','manager') AND r.scope_type='tenant')
   OR (r.role='manager' AND r.scope_type='site' AND r.site_id=site))
 ) THEN RETURN; END IF;
 -- Explicit source must exist and belong to this case; never allow cross-tenant IDs.
 IF p_source IS NOT NULL AND NOT EXISTS (
  SELECT 1 FROM sme.discovery_sources s
  WHERE s.tenant_id=p_tenant AND s.case_id=p_case AND s.id=p_source
 ) THEN RETURN; END IF;
 INSERT INTO sme.discovery_requirements
   (tenant_id,id,case_id,source_id,statement,classification,approval_state)
 VALUES(p_tenant,p_req,p_case,p_source,normalized_statement,p_classification,'proposed')
 ON CONFLICT (tenant_id,id) DO NOTHING;
 GET DIAGNOSTICS inserted=ROW_COUNT;
 IF inserted=0 THEN
   SELECT r.case_id,r.source_id,r.statement,r.classification INTO prior
   FROM sme.discovery_requirements r
   WHERE r.tenant_id=p_tenant AND r.id=p_req;
   IF NOT FOUND THEN RAISE EXCEPTION 'requirement replay unavailable'; END IF;
   IF prior.case_id IS DISTINCT FROM p_case OR prior.source_id IS DISTINCT FROM p_source
      OR prior.statement IS DISTINCT FROM normalized_statement
      OR prior.classification IS DISTINCT FROM p_classification THEN
    RETURN QUERY SELECT p_req,true,true;
    RETURN;
   END IF;
   RETURN QUERY SELECT p_req,true,false;
   RETURN;
 END IF;
 INSERT INTO sme.discovery_change_events
  (tenant_id,case_id,actor_identity_id,action,subject_id)
 VALUES (p_tenant,p_case,actor,'requirement.created',p_req);
 RETURN QUERY SELECT p_req,false,false;
END $$;
ALTER FUNCTION sme.create_discovery_requirement_once(bytea,uuid,uuid,uuid,text,text,uuid)
 OWNER TO sme_discovery_service;
REVOKE ALL ON FUNCTION sme.create_discovery_requirement_once(bytea,uuid,uuid,uuid,text,text,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION sme.create_discovery_requirement_once(bytea,uuid,uuid,uuid,text,text,uuid) TO sme_app;
COMMIT;
