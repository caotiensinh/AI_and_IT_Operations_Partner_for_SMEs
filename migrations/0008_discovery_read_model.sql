-- Research discovery read model. Requires 0001-0007 and PostgreSQL 15+.
-- No application writes: audited provisioning/import service is future work.
BEGIN;
CREATE TABLE IF NOT EXISTS sme.discovery_cases (
 tenant_id uuid NOT NULL,
 id uuid NOT NULL,
 site_id uuid NOT NULL,
 label text NOT NULL CHECK (length(trim(label)) BETWEEN 1 AND 200),
 company_code text NOT NULL CHECK (company_code IN ('B','J','L','R','OTHER')),
 status text NOT NULL DEFAULT 'research' CHECK (status IN ('research','review','closed')),
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (tenant_id,id),
 FOREIGN KEY (tenant_id,site_id) REFERENCES sme.sites(tenant_id,id)
);
CREATE TABLE IF NOT EXISTS sme.discovery_sources (
 tenant_id uuid NOT NULL,
 id uuid NOT NULL,
 case_id uuid NOT NULL,
 document_label text NOT NULL CHECK (length(trim(document_label)) BETWEEN 1 AND 200),
 source_page integer NOT NULL CHECK (source_page>=1),
 visibility text NOT NULL DEFAULT 'private' CHECK (visibility='private'),
 PRIMARY KEY (tenant_id,id),
 UNIQUE (tenant_id,case_id,id),
 FOREIGN KEY (tenant_id,case_id) REFERENCES sme.discovery_cases(tenant_id,id)
);
CREATE TABLE IF NOT EXISTS sme.discovery_requirements (
 tenant_id uuid NOT NULL,
 id uuid NOT NULL,
 case_id uuid NOT NULL,
 source_id uuid,
 statement text NOT NULL CHECK (length(trim(statement)) BETWEEN 1 AND 4000),
 classification text NOT NULL CHECK (classification IN ('explicit','inferred','unverified')),
 approval_state text NOT NULL DEFAULT 'proposed'
  CHECK (approval_state IN ('proposed','confirmed','rejected')),
 PRIMARY KEY (tenant_id,id),
 FOREIGN KEY (tenant_id,case_id) REFERENCES sme.discovery_cases(tenant_id,id),
 FOREIGN KEY (tenant_id,case_id,source_id)
  REFERENCES sme.discovery_sources(tenant_id,case_id,id),
 CHECK (classification<>'explicit' OR source_id IS NOT NULL),
 CHECK (classification='explicit' OR approval_state<>'confirmed')
);
CREATE INDEX IF NOT EXISTS discovery_cases_site_idx ON sme.discovery_cases(tenant_id,site_id);
CREATE INDEX IF NOT EXISTS discovery_requirements_case_idx ON sme.discovery_requirements(tenant_id,case_id);
-- RLS applies to owner as well, unless a privileged migration owner is used;
-- sme_app is read-only and MUST have authenticated tenant context set by API.
ALTER TABLE sme.discovery_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE sme.discovery_cases FORCE ROW LEVEL SECURITY;
ALTER TABLE sme.discovery_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE sme.discovery_sources FORCE ROW LEVEL SECURITY;
ALTER TABLE sme.discovery_requirements ENABLE ROW LEVEL SECURITY;
ALTER TABLE sme.discovery_requirements FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS discovery_cases_tenant ON sme.discovery_cases;
CREATE POLICY discovery_cases_tenant ON sme.discovery_cases TO sme_app
 USING (tenant_id=sme.current_tenant());
DROP POLICY IF EXISTS discovery_sources_tenant ON sme.discovery_sources;
CREATE POLICY discovery_sources_tenant ON sme.discovery_sources TO sme_app
 USING (tenant_id=sme.current_tenant());
DROP POLICY IF EXISTS discovery_requirements_tenant ON sme.discovery_requirements;
CREATE POLICY discovery_requirements_tenant ON sme.discovery_requirements TO sme_app
 USING (tenant_id=sme.current_tenant());
REVOKE ALL ON sme.discovery_cases,sme.discovery_sources,sme.discovery_requirements FROM PUBLIC;
GRANT SELECT ON sme.discovery_cases,sme.discovery_sources,sme.discovery_requirements TO sme_app;
COMMIT;
