-- Metadata-only source intake for discovery research cases. Requires 0007.
-- Client-supplied source UUID is a stable retry identity; never a grant of access.
BEGIN;
GRANT SELECT ON sme.discovery_cases TO sme_discovery_service;
DROP POLICY IF EXISTS discovery_writer_case_read ON sme.discovery_cases;
CREATE POLICY discovery_writer_case_read ON sme.discovery_cases
 FOR SELECT TO sme_discovery_service USING (tenant_id=sme.current_tenant());
GRANT SELECT,INSERT ON sme.discovery_sources TO sme_discovery_service;
DROP POLICY IF EXISTS discovery_writer_source_read ON sme.discovery_sources;
CREATE POLICY discovery_writer_source_read ON sme.discovery_sources
 FOR SELECT TO sme_discovery_service USING (tenant_id=sme.current_tenant());
DROP POLICY IF EXISTS discovery_writer_source_insert ON sme.discovery_sources;
CREATE POLICY discovery_writer_source_insert ON sme.discovery_sources
 FOR INSERT TO sme_discovery_service WITH CHECK (tenant_id=sme.current_tenant());
ALTER TABLE sme.discovery_change_events ADD COLUMN IF NOT EXISTS subject_id uuid;
ALTER TABLE sme.discovery_change_events
 DROP CONSTRAINT IF EXISTS discovery_change_events_action_check;
ALTER TABLE sme.discovery_change_events
 ADD CONSTRAINT discovery_change_events_action_check
 CHECK (action IN ('case.created','source.created'));
CREATE OR REPLACE FUNCTION sme.create_discovery_source_once(
 p_digest bytea,p_tenant uuid,p_case uuid,p_source uuid,p_label text,p_page integer
) RETURNS TABLE(result_source_id uuid,is_replay boolean,is_conflict boolean)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,sme
AS $$
DECLARE
 actor uuid;
 site uuid;
 prior record;
 inserted integer;
 normalized_label text;
BEGIN
 IF p_digest IS NULL OR octet_length(p_digest)<>32
    OR p_tenant IS NULL OR p_case IS NULL OR p_source IS NULL
    OR p_label IS NULL OR length(btrim(p_label)) NOT BETWEEN 1 AND 200
    OR p_page IS NULL OR p_page<1 THEN RETURN; END IF;
 normalized_label:=btrim(p_label);
 actor:=sme.resolve_session(p_digest,p_tenant);
 IF actor IS NULL THEN RETURN; END IF;
 PERFORM set_config('sme.tenant_id',p_tenant::text,true);
 SELECT c.site_id INTO site FROM sme.discovery_cases c
 WHERE c.tenant_id=p_tenant AND c.id=p_case AND c.status='research';
 IF NOT FOUND THEN RETURN; END IF;
 -- Only verified owners/admins/managers with scope over the case's site.
 IF NOT EXISTS (
  SELECT 1 FROM sme.role_assignments r
  WHERE r.tenant_id=p_tenant AND r.identity_id=actor
   AND ((r.role IN ('owner','admin','manager') AND r.scope_type='tenant')
   OR (r.role='manager' AND r.scope_type='site' AND r.site_id=site))
 ) THEN RETURN; END IF;
 INSERT INTO sme.discovery_sources(tenant_id,id,case_id,document_label,source_page)
 VALUES(p_tenant,p_source,p_case,normalized_label,p_page)
 ON CONFLICT (tenant_id,id) DO NOTHING;
 GET DIAGNOSTICS inserted=ROW_COUNT;
 IF inserted=0 THEN
  SELECT s.case_id,s.document_label,s.source_page INTO prior
  FROM sme.discovery_sources s WHERE s.tenant_id=p_tenant AND s.id=p_source;
  IF NOT FOUND THEN RAISE EXCEPTION 'source replay unavailable'; END IF;
  IF prior.case_id IS DISTINCT FROM p_case OR prior.document_label IS DISTINCT FROM normalized_label
     OR prior.source_page IS DISTINCT FROM p_page THEN
    RETURN QUERY SELECT p_source,true,true;
    RETURN;
  END IF;
  RETURN QUERY SELECT p_source,true,false;
  RETURN;
 END IF;
 INSERT INTO sme.discovery_change_events
   (tenant_id,case_id,actor_identity_id,action,subject_id)
 VALUES (p_tenant,p_case,actor,'source.created',p_source);
 RETURN QUERY SELECT p_source,false,false;
END $$;
ALTER FUNCTION sme.create_discovery_source_once(bytea,uuid,uuid,uuid,text,integer)
 OWNER TO sme_discovery_service;
REVOKE ALL ON FUNCTION sme.create_discovery_source_once(bytea,uuid,uuid,uuid,text,integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION sme.create_discovery_source_once(bytea,uuid,uuid,uuid,text,integer) TO sme_app;
COMMIT;
