-- Read-only manager view of requirement review history, migration after 0010.
BEGIN;
GRANT SELECT ON sme.discovery_requirement_reviews TO sme_discovery_service;
DROP POLICY IF EXISTS discovery_review_reader ON sme.discovery_requirement_reviews;
CREATE POLICY discovery_review_reader ON sme.discovery_requirement_reviews
 FOR SELECT TO sme_discovery_service USING (tenant_id=sme.current_tenant());

CREATE OR REPLACE FUNCTION sme.get_discovery_requirement_review_history(
 p_digest bytea,p_tenant uuid,p_case uuid,p_requirement uuid
) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path=pg_catalog,sme
AS $$
DECLARE
 actor uuid;
 site uuid;
 req_state text;
 req_version integer;
 records jsonb;
BEGIN
 IF p_digest IS NULL OR octet_length(p_digest)<>32
    OR p_tenant IS NULL OR p_case IS NULL OR p_requirement IS NULL THEN
   RETURN NULL;
 END IF;
 actor:=sme.resolve_session(p_digest,p_tenant);
 IF actor IS NULL THEN RETURN NULL; END IF;
 PERFORM set_config('sme.tenant_id',p_tenant::text,true);
 SELECT c.site_id INTO site FROM sme.discovery_cases c
 WHERE c.tenant_id=p_tenant AND c.id=p_case;
 IF NOT FOUND THEN RETURN NULL; END IF;
 IF NOT EXISTS (
  SELECT 1 FROM sme.role_assignments ra
  WHERE ra.tenant_id=p_tenant AND ra.identity_id=actor
    AND ((ra.role IN ('owner','admin','manager') AND ra.scope_type='tenant')
      OR (ra.role='manager' AND ra.scope_type='site' AND ra.site_id=site))
 ) THEN RETURN NULL; END IF;
 SELECT r.approval_state,r.review_version INTO req_state,req_version
 FROM sme.discovery_requirements r
 WHERE r.tenant_id=p_tenant AND r.case_id=p_case AND r.id=p_requirement;
 IF NOT FOUND THEN RETURN NULL; END IF;
 SELECT COALESCE(jsonb_agg(jsonb_build_object(
      'version',rv.review_version,
      'previous_state',rv.previous_state,
      'next_state',rv.next_state,
      'rationale',rv.rationale,
      'reviewer_id',rv.actor_identity_id,
      'reviewed_at',rv.created_at
    ) ORDER BY rv.review_version),'[]'::jsonb)
 INTO records
 FROM sme.discovery_requirement_reviews rv
 WHERE rv.tenant_id=p_tenant AND rv.case_id=p_case AND rv.requirement_id=p_requirement;
 RETURN jsonb_build_object('approval_state',req_state,
                           'review_version',req_version,
                           'reviews',records);
END $$;
ALTER FUNCTION sme.get_discovery_requirement_review_history(bytea,uuid,uuid,uuid)
 OWNER TO sme_discovery_service;
REVOKE ALL ON FUNCTION sme.get_discovery_requirement_review_history(bytea,uuid,uuid,uuid)
 FROM PUBLIC;
GRANT EXECUTE ON FUNCTION sme.get_discovery_requirement_review_history(bytea,uuid,uuid,uuid)
 TO sme_app;
COMMIT;
