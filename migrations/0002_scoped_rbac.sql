-- M1.2 scoped authorization schema. Run after 0001 via migration owner.
-- IMPORTANT: runtime app can READ assignments but cannot mint/change privileges.
BEGIN;
CREATE TABLE IF NOT EXISTS sme.departments (
 tenant_id uuid NOT NULL,
 id uuid NOT NULL,
 site_id uuid NOT NULL,
 parent_id uuid,
 label text NOT NULL CHECK(length(label)>0),
 PRIMARY KEY (tenant_id,id),
 UNIQUE (tenant_id,site_id,id),
 FOREIGN KEY (tenant_id,site_id) REFERENCES sme.sites(tenant_id,id),
 FOREIGN KEY (tenant_id,site_id,parent_id) REFERENCES sme.departments(tenant_id,site_id,id)
);
CREATE TABLE IF NOT EXISTS sme.role_assignments (
 tenant_id uuid NOT NULL,
 id uuid NOT NULL,
 identity_id uuid NOT NULL,
 role text NOT NULL CHECK(role IN ('owner','admin','manager','operator','viewer')),
 scope_type text NOT NULL CHECK(scope_type IN ('tenant','site','department')),
 site_id uuid,
 department_id uuid,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (tenant_id,id),
 FOREIGN KEY (tenant_id,identity_id) REFERENCES sme.memberships(tenant_id,identity_id),
 FOREIGN KEY (tenant_id,site_id) REFERENCES sme.sites(tenant_id,id),
 FOREIGN KEY (tenant_id,department_id) REFERENCES sme.departments(tenant_id,id),
 CHECK (
  (scope_type='tenant' AND site_id IS NULL AND department_id IS NULL)
  OR (scope_type='site' AND site_id IS NOT NULL AND department_id IS NULL)
  OR (scope_type='department' AND site_id IS NULL AND department_id IS NOT NULL)
 ),
 CHECK (role NOT IN ('owner','admin') OR scope_type='tenant')
);
CREATE INDEX IF NOT EXISTS idx_role_assignment_identity ON sme.role_assignments(tenant_id,identity_id);
ALTER TABLE sme.departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE sme.departments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_departments ON sme.departments;
CREATE POLICY tenant_departments ON sme.departments TO sme_app
 USING (tenant_id=sme.current_tenant()) WITH CHECK (tenant_id=sme.current_tenant());
ALTER TABLE sme.role_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE sme.role_assignments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_roles ON sme.role_assignments;
CREATE POLICY tenant_roles ON sme.role_assignments TO sme_app
 USING (tenant_id=sme.current_tenant()) WITH CHECK (tenant_id=sme.current_tenant());
GRANT SELECT ON sme.departments,sme.role_assignments TO sme_app;
-- Do not GRANT INSERT/UPDATE/DELETE on role_assignments to sme_app.
-- A dedicated administrative service with reviewed step-up/approval flow is required.
COMMIT;
