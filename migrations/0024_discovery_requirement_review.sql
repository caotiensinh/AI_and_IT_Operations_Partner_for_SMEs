-- Spec 003: requirement review is NOT customer acceptance or deployment approval.
-- Migration after 0009; PostgreSQL 15+, run as provisioning owner.
BEGIN;
ALTER TABLE sme.discovery_requirements
 ADD COLUMN IF NOT EXISTS review_version integer NOT NULL DEFAULT 0
 CHECK (review_version >= 0);
GRANT UPDATE (approval_state,review_version) ON sme.discovery_requirements
 TO sme_discovery_service;
DROP POLICY IF EXISTS discovery_writer_requirement_update ON sme.discovery_requirements;
CREATE POLICY discovery_writer_requirement_update ON sme.discovery_requirements
 FOR UPDATE TO sme_discovery_service
 USING (tenant_id=sme.current_tenant())
 WITH CHECK (tenant_id=sme.current_tenant());

CREATE TABLE IF NOT EXISTS sme.discovery_requirement_reviews (
 tenant_id uuid NOT NULL,
 id uuid NOT NULL DEFAULT gen_random_uuid(),
 case_id uuid NOT NULL,
 requirement_id uuid NOT NULL,
 actor_identity_id uuid NOT NULL,
 previous_state text NOT NULL CHECK (previous_state IN ('proposed','confirmed','rejected')),
 next_state text NOT NULL CHECK (next_state IN ('confirmed','rejected')),
 review_version integer NOT NULL CHECK(review_version>0),
 rationale text NOT NULL CHECK(length(btrim(rationale)) BETWEEN 8 AND 2000),
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant_id,id),
 UNIQUE(tenant_id,requirement_id,review_version),
 FOREIGN KEY(tenant_id,requirement_id) REFERENCES sme.discovery_requirements(tenant_id,id),
 FOREIGN KEY(tenant_id,case_id) REFERENCES sme.discovery_cases(tenant_id,id),
 FOREIGN KEY(actor_identity_id) REFERENCES sme.identities(id)
);
ALTER TABLE sme.discovery_requirement_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE sme.discovery_requirement_reviews FORCE ROW LEVEL SECURITY;
REVOKE ALL ON sme.discovery_requirement_reviews FROM PUBLIC,sme_app;
GRANT INSERT ON sme.discovery_requirement_reviews TO sme_discovery_service;
DROP POLICY IF EXISTS discovery_review_insert ON sme.discovery_requirement_reviews;
CREATE POLICY discovery_review_insert ON sme.discovery_requirement_reviews
 FOR INSERT TO sme_discovery_service WITH CHECK(tenant_id=sme.current_tenant());
ALTER TABLE sme.discovery_change_events
 DROP CONSTRAINT IF EXISTS discovery_change_events_action_check;
ALTER TABLE sme.discovery_change_events
 ADD CONSTRAINT discovery_change_events_action_check
 CHECK(action IN ('case.created','source.created','requirement.created','requirement.reviewed'));

CREATE OR REPLACE FUNCTION sme.review_discovery_requirement(
 p_digest bytea,p_tenant uuid,p_case uuid,p_requirement uuid,
 p_expected_version integer,p_decision text,p_rationale text
) RETURNS TABLE(result_status text,result_version integer,result_state text)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,sme
AS $$
DECLARE
 actor uuid;
 site uuid;
 item record;
 notes text;
BEGIN
 IF p_digest IS NULL OR octet_length(p_digest)<>32
    OR p_tenant IS NULL OR p_case IS NULL OR p_requirement IS NULL
    OR p_expected_version IS NULL OR p_expected_version<0
    OR p_decision NOT IN ('confirmed','rejected') OR p_decision IS NULL
    OR p_rationale IS NULL OR length(btrim(p_rationale)) NOT BETWEEN 8 AND 2000 THEN
  RETURN QUERY SELECT 'invalid'::text,NULL::integer,NULL::text;
  RETURN;
 END IF;
 notes:=btrim(p_rationale);
 actor:=sme.resolve_session(p_digest,p_tenant);
 IF actor IS NULL THEN
  RETURN QUERY SELECT 'denied'::text,NULL::integer,NULL::text;
  RETURN;
 END IF;
 PERFORM set_config('sme.tenant_id',p_tenant::text,true);
 SELECT c.site_id INTO site FROM sme.discovery_cases c
 WHERE c.tenant_id=p_tenant AND c.id=p_case AND c.status='research';
 IF NOT FOUND THEN
  RETURN QUERY SELECT 'denied'::text,NULL::integer,NULL::text;
  RETURN;
 END IF;
 IF NOT EXISTS (
  SELECT 1 FROM sme.role_assignments ra
  WHERE ra.tenant_id=p_tenant AND ra.identity_id=actor
    AND ((ra.role IN ('owner','admin','manager') AND ra.scope_type='tenant')
      OR (ra.role='manager' AND ra.scope_type='site' AND ra.site_id=site))
 ) THEN
  RETURN QUERY SELECT 'denied'::text,NULL::integer,NULL::text;
  RETURN;
 END IF;
 -- Row lock serializes concurrent decisions. RLS still enforces tenant boundary.
 SELECT r.review_version,r.approval_state,r.classification,r.source_id
 INTO item
 FROM sme.discovery_requirements r
 WHERE r.tenant_id=p_tenant AND r.case_id=p_case AND r.id=p_requirement
 FOR UPDATE;
 IF NOT FOUND THEN
  RETURN QUERY SELECT 'denied'::text,NULL::integer,NULL::text;
  RETURN;
 END IF;
 IF item.review_version<>p_expected_version THEN
  RETURN QUERY SELECT 'conflict'::text,item.review_version,item.approval_state;
  RETURN;
 END IF;
 IF item.approval_state=p_decision THEN
  RETURN QUERY SELECT 'unchanged'::text,item.review_version,item.approval_state;
  RETURN;
 END IF;
 -- No approvals by inference, and terminal decisions cannot silently flip.
 IF item.approval_state<>'proposed'
    OR (p_decision='confirmed' AND
        (item.classification<>'explicit' OR item.source_id IS NULL)) THEN
  RETURN QUERY SELECT 'invalid'::text,item.review_version,item.approval_state;
  RETURN;
 END IF;
 UPDATE sme.discovery_requirements r
 SET approval_state=p_decision,review_version=r.review_version+1
 WHERE r.tenant_id=p_tenant AND r.case_id=p_case AND r.id=p_requirement;
 INSERT INTO sme.discovery_requirement_reviews
  (tenant_id,case_id,requirement_id,actor_identity_id,previous_state,
   next_state,review_version,rationale)
 VALUES(p_tenant,p_case,p_requirement,actor,item.approval_state,
        p_decision,item.review_version+1,notes);
 INSERT INTO sme.discovery_change_events
  (tenant_id,case_id,actor_identity_id,action,subject_id)
 VALUES(p_tenant,p_case,actor,'requirement.reviewed',p_requirement);
 RETURN QUERY SELECT 'updated'::text,item.review_version+1,p_decision;
END $$;
ALTER FUNCTION sme.review_discovery_requirement(bytea,uuid,uuid,uuid,integer,text,text)
 OWNER TO sme_discovery_service;
REVOKE ALL ON FUNCTION sme.review_discovery_requirement(bytea,uuid,uuid,uuid,integer,text,text)
 FROM PUBLIC;
GRANT EXECUTE ON FUNCTION sme.review_discovery_requirement(bytea,uuid,uuid,uuid,integer,text,text)
 TO sme_app;
COMMIT;
