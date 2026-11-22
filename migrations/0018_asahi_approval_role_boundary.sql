-- Spec 018: isolate approval function execution from general app role.
-- No activation of a production approval service or MFA claims.
BEGIN;
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sme_approval') THEN
  CREATE ROLE sme_approval NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
 END IF;
END $$;
-- Reaffirm privilege boundary on every migration replay.
ALTER ROLE sme_approval NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
GRANT USAGE ON SCHEMA sme TO sme_approval;
REVOKE ALL ON FUNCTION sme.approve_asahi_delivery(bytea,uuid,text,text,text)
 FROM PUBLIC,sme_app,sme_auth,sme_ingest,sme_dispatch;
REVOKE ALL ON FUNCTION sme.revoke_asahi_delivery(bytea,uuid)
 FROM PUBLIC,sme_app,sme_auth,sme_ingest,sme_dispatch;
GRANT EXECUTE ON FUNCTION sme.approve_asahi_delivery(bytea,uuid,text,text,text)
 TO sme_approval;
GRANT EXECUTE ON FUNCTION sme.revoke_asahi_delivery(bytea,uuid)
 TO sme_approval;
-- The role has no table access, session issue rights, membership or OIDC write.
REVOKE ALL ON sme.asahi_delivery_destinations,sme.asahi_delivery_policy_audit
 FROM sme_approval;
REVOKE ALL ON sme.sessions,sme.memberships,sme.role_assignments
 FROM sme_approval;
REVOKE ALL ON FUNCTION sme.issue_oidc_session(text,text,bytea,integer)
 FROM sme_approval;
COMMIT;
