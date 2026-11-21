-- Requires PostgreSQL 15+. Migration owner is never application DB role.
BEGIN;
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sme_app') THEN
   CREATE ROLE sme_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
 END IF;
END $$;
CREATE SCHEMA IF NOT EXISTS sme;
REVOKE ALL ON SCHEMA sme FROM PUBLIC;
GRANT USAGE ON SCHEMA sme TO sme_app;
CREATE TABLE IF NOT EXISTS sme.tenants (
 id uuid PRIMARY KEY,
 slug text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,62}$'),
 display_name text NOT NULL CHECK (length(display_name)>0),
 status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended')),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS sme.identities (
 id uuid PRIMARY KEY,
 issuer text NOT NULL CHECK (length(issuer)>0),
 subject text NOT NULL CHECK (length(subject)>0),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (issuer,subject)
);
CREATE TABLE IF NOT EXISTS sme.memberships (
 tenant_id uuid NOT NULL REFERENCES sme.tenants(id) ON DELETE RESTRICT,
 identity_id uuid NOT NULL REFERENCES sme.identities(id) ON DELETE RESTRICT,
 status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','invited','disabled')),
 PRIMARY KEY (tenant_id,identity_id)
);
CREATE TABLE IF NOT EXISTS sme.sites (
 tenant_id uuid NOT NULL REFERENCES sme.tenants(id),
 id uuid NOT NULL,
 label text NOT NULL CHECK (length(label)>0),
 PRIMARY KEY (tenant_id,id)
);
CREATE TABLE IF NOT EXISTS sme.assets (
 tenant_id uuid NOT NULL,
 id uuid NOT NULL,
 site_id uuid NOT NULL,
 name text NOT NULL CHECK (length(name)>0),
 PRIMARY KEY (tenant_id,id),
 FOREIGN KEY (tenant_id,site_id) REFERENCES sme.sites(tenant_id,id)
);
CREATE INDEX IF NOT EXISTS idx_assets_site ON sme.assets (tenant_id,site_id);
-- GUC set only after independently authenticated server-side tenant membership.
CREATE OR REPLACE FUNCTION sme.current_tenant() RETURNS uuid
LANGUAGE plpgsql STABLE AS $$
DECLARE raw text;
BEGIN
 raw := current_setting('sme.tenant_id', true);
 IF raw IS NULL OR raw = '' THEN RETURN NULL; END IF;
 BEGIN RETURN raw::uuid;
 EXCEPTION WHEN invalid_text_representation THEN RETURN NULL;
 END;
END $$;
REVOKE ALL ON FUNCTION sme.current_tenant() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION sme.current_tenant() TO sme_app;
-- Provisioning uses a separately audited role; no app grants on tenants/identities.
GRANT SELECT, INSERT, UPDATE, DELETE ON sme.memberships,sme.sites,sme.assets TO sme_app;
ALTER TABLE sme.memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE sme.memberships FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_memberships ON sme.memberships;
CREATE POLICY tenant_memberships ON sme.memberships TO sme_app
 USING (tenant_id = sme.current_tenant()) WITH CHECK (tenant_id = sme.current_tenant());
ALTER TABLE sme.sites ENABLE ROW LEVEL SECURITY;
ALTER TABLE sme.sites FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_sites ON sme.sites;
CREATE POLICY tenant_sites ON sme.sites TO sme_app
 USING (tenant_id = sme.current_tenant()) WITH CHECK (tenant_id = sme.current_tenant());
ALTER TABLE sme.assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE sme.assets FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_assets ON sme.assets;
CREATE POLICY tenant_assets ON sme.assets TO sme_app
 USING (tenant_id = sme.current_tenant()) WITH CHECK (tenant_id = sme.current_tenant());
COMMIT;
