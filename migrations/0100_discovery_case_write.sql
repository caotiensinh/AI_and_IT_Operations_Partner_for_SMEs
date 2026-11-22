-- Spec 003: narrow case-creation capability with a separate SECURITY DEFINER role.
-- Run after 0005 as migration owner. No customer data in the migration.
BEGIN;
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sme_discovery_service') THEN
  CREATE ROLE sme_discovery_service NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
 END IF;
END $$;
GRANT USAGE ON SCHEMA sme TO sme_discovery_service;
GRANT EXECUTE ON FUNCTION sme.resolve_session(bytea,uuid) TO sme_discovery_service;
GRANT EXECUTE ON FUNCTION sme.current_tenant() TO sme_discovery_service;
GRANT SELECT ON sme.role_assignments,sme.sites TO sme_discovery_service;
GRANT INSERT ON sme.discovery_cases TO sme_discovery_service;
-- Discoverable tenant context is set only after the DB verifies bearer digest.
DROP POLICY IF EXISTS discovery_writer_roles ON sme.role_assignments;
CREATE POLICY discovery_writer_roles ON sme.role_assignments FOR SELECT TO sme_discovery_service
 USING (tenant_id=sme.current_tenant());
DROP POLICY IF EXISTS discovery_writer_sites ON sme.sites;
CREATE POLICY discovery_writer_sites ON sme.sites FOR SELECT TO sme_discovery_service
 USING (tenant_id=sme.current_tenant());
DROP POLICY IF EXISTS discovery_writer_create ON sme.discovery_cases;
CREATE POLICY discovery_writer_create ON sme.discovery_cases FOR INSERT TO sme_discovery_service
 WITH CHECK (tenant_id=sme.current_tenant());

CREATE TABLE IF NOT EXISTS sme.discovery_change_events (
 tenant_id uuid NOT NULL,
 id uuid NOT NULL DEFAULT gen_random_uuid(),
 case_id uuid NOT NULL,
 actor_identity_id uuid NOT NULL,
 action text NOT NULL CHECK (action='case.created'),
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant_id,id),
 FOREIGN KEY(tenant_id,case_id) REFERENCES sme.discovery_cases(tenant_id,id),
 FOREIGN KEY(actor_identity_id) REFERENCES sme.identities(id)
);
ALTER TABLE sme.discovery_change_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE sme.discovery_change_events FORCE ROW LEVEL SECURITY;
REVOKE ALL ON sme.discovery_change_events FROM PUBLIC,sme_app;
GRANT INSERT ON sme.discovery_change_events TO sme_discovery_service;
DROP POLICY IF EXISTS discovery_events_insert ON sme.discovery_change_events;
CREATE POLICY discovery_events_insert ON sme.discovery_change_events
 FOR INSERT TO sme_discovery_service
 WITH CHECK (tenant_id=sme.current_tenant());

-- Runtime can EXECUTE, but never SELECT membership tables or INSERT records directly.
CREATE OR REPLACE FUNCTION sme.create_discovery_case(
 p_digest bytea,p_tenant uuid,p_site uuid,p_label text,p_company text
) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,sme
AS $$
DECLARE
 actor uuid;
 case_id uuid;
BEGIN
 IF p_digest IS NULL OR octet_length(p_digest)<>32
    OR p_tenant IS NULL OR p_site IS NULL
    OR p_label IS NULL OR length(btrim(p_label)) NOT BETWEEN 1 AND 200
    OR p_company NOT IN ('B','J','L','R','OTHER') THEN
   RETURN NULL;
 END IF;
 actor := sme.resolve_session(p_digest,p_tenant);
 IF actor IS NULL THEN RETURN NULL; END IF;
 PERFORM set_config('sme.tenant_id',p_tenant::text,true);
 -- Require a real site in the authenticated tenant.
 IF NOT EXISTS (SELECT 1 FROM sme.sites WHERE tenant_id=p_tenant AND id=p_site) THEN
   RETURN NULL;
 END IF;
 -- Only owners/admins at tenant scope or managers assigned to the requested site.
 IF NOT EXISTS (
   SELECT 1 FROM sme.role_assignments ra
   WHERE ra.tenant_id=p_tenant AND ra.identity_id=actor
     AND (
       (ra.role IN ('owner','admin') AND ra.scope_type='tenant')
       OR (ra.role='manager' AND ra.scope_type='tenant')
       OR (ra.role='manager' AND ra.scope_type='site' AND ra.site_id=p_site)
     )
 ) THEN RETURN NULL; END IF;
 case_id := gen_random_uuid();
 INSERT INTO sme.discovery_cases(tenant_id,id,site_id,label,company_code,status)
 VALUES (p_tenant,case_id,p_site,btrim(p_label),p_company,'research');
 INSERT INTO sme.discovery_change_events(tenant_id,case_id,actor_identity_id,action)
 VALUES (p_tenant,case_id,actor,'case.created');
 RETURN case_id;
END $$;
ALTER FUNCTION sme.create_discovery_case(bytea,uuid,uuid,text,text)
 OWNER TO sme_discovery_service;
REVOKE ALL ON FUNCTION sme.create_discovery_case(bytea,uuid,uuid,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION sme.create_discovery_case(bytea,uuid,uuid,text,text) TO sme_app;
COMMIT;
