-- Spec 019: single-use action-bound step-up proof database boundary.
-- This is NOT an IdP MFA verifier; issuer role remains NOLOGIN/unprovisioned.
BEGIN;
DO $roles$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sme_stepup') THEN
   CREATE ROLE sme_stepup NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
 END IF;
END $roles$;
ALTER ROLE sme_stepup NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
GRANT USAGE ON SCHEMA sme TO sme_stepup;
CREATE TABLE IF NOT EXISTS sme.asahi_stepup_proofs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 session_digest bytea NOT NULL CHECK(octet_length(session_digest)=32),
 tenant_id uuid NOT NULL REFERENCES sme.tenants(id),
 actor_id uuid NOT NULL REFERENCES sme.identities(id),
 action text NOT NULL CHECK(action IN ('approve','revoke')),
 channel text,
 destination_ref text,
 secret_ref text,
 issued_at timestamptz NOT NULL DEFAULT now(),
 expires_at timestamptz NOT NULL,
 consumed_at timestamptz,
 CHECK (expires_at > issued_at AND expires_at <= issued_at + interval '120 seconds'),
 CHECK (
  (action='revoke' AND channel IS NULL AND destination_ref IS NULL AND secret_ref IS NULL)
  OR (action='approve' AND channel IN ('email','webhook')
      AND destination_ref ~ '^[A-Za-z0-9_./-]{1,128}$'
      AND secret_ref ~ '^[A-Za-z0-9_./-]{1,128}$'
      AND destination_ref !~ '(^|/)[.][.](/|$)'
      AND secret_ref !~ '(^|/)[.][.](/|$)'
      AND left(destination_ref,1)<>'/' AND left(secret_ref,1)<>'/')
 )
);
CREATE INDEX IF NOT EXISTS ix_asahi_stepup_expiry
 ON sme.asahi_stepup_proofs(expires_at) WHERE consumed_at IS NULL;
REVOKE ALL ON sme.asahi_stepup_proofs
 FROM PUBLIC,sme_app,sme_auth,sme_ingest,sme_dispatch,sme_approval,sme_stepup;
ALTER TABLE sme.asahi_stepup_proofs ENABLE ROW LEVEL SECURITY;
-- SECURITY DEFINER migration owner must access rows; runtime roles have no table grants.

-- The role sme_stepup is intentionally NOT granted to an application login.
-- A trusted service must verify fresh IdP MFA before calling this function.
CREATE OR REPLACE FUNCTION sme.issue_asahi_stepup(
 p_digest bytea,p_tenant uuid,p_action text,p_channel text,
 p_destination_ref text,p_secret_ref text,p_lifetime integer DEFAULT 60
) RETURNS uuid LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,sme AS $body$
DECLARE actor uuid; proof uuid;
BEGIN
 IF p_digest IS NULL OR octet_length(p_digest)<>32 OR p_tenant IS NULL
    OR p_action NOT IN ('approve','revoke') OR p_action IS NULL
    OR p_lifetime IS NULL OR p_lifetime NOT BETWEEN 15 AND 120 THEN RETURN NULL; END IF;
 IF p_action='approve' AND (
     p_channel NOT IN ('email','webhook') OR p_channel IS NULL
     OR p_destination_ref IS NULL OR p_secret_ref IS NULL
     OR p_destination_ref !~ '^[A-Za-z0-9_./-]{1,128}$'
     OR p_secret_ref !~ '^[A-Za-z0-9_./-]{1,128}$'
     OR p_destination_ref ~ '(^|/)[.][.](/|$)'
     OR p_secret_ref ~ '(^|/)[.][.](/|$)'
     OR left(p_destination_ref,1)='/' OR left(p_secret_ref,1)='/'
 ) THEN RETURN NULL; END IF;
 IF p_action='revoke' AND (
    p_channel IS NOT NULL OR p_destination_ref IS NOT NULL
    OR p_secret_ref IS NOT NULL
 ) THEN RETURN NULL; END IF;
 SELECT sme.resolve_session(p_digest,p_tenant) INTO actor;
 IF actor IS NULL OR NOT EXISTS (
   SELECT 1 FROM sme.role_assignments r
   WHERE r.tenant_id=p_tenant AND r.identity_id=actor
     AND r.role='owner' AND r.scope_type='tenant'
 ) THEN RETURN NULL; END IF;
 INSERT INTO sme.asahi_stepup_proofs(
  session_digest,tenant_id,actor_id,action,channel,destination_ref,
  secret_ref,expires_at
 ) VALUES (
  p_digest,p_tenant,actor,p_action,p_channel,p_destination_ref,
  p_secret_ref,now()+make_interval(secs=>p_lifetime)
 ) RETURNING id INTO proof;
 RETURN proof;
END $body$;

CREATE OR REPLACE FUNCTION sme.approve_asahi_delivery_stepup(
 p_digest bytea,p_tenant uuid,p_proof uuid,p_channel text,
 p_destination_ref text,p_secret_ref text
) RETURNS boolean LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,sme AS $body$
DECLARE actor uuid; proof_id uuid;
BEGIN
 IF p_digest IS NULL OR octet_length(p_digest)<>32
    OR p_tenant IS NULL OR p_proof IS NULL THEN RETURN false; END IF;
 SELECT sme.resolve_session(p_digest,p_tenant) INTO actor;
 IF actor IS NULL THEN RETURN false; END IF;
 UPDATE sme.asahi_stepup_proofs p SET consumed_at=now()
 WHERE p.id=p_proof AND p.session_digest=p_digest AND p.tenant_id=p_tenant
   AND p.actor_id=actor AND p.action='approve' AND p.consumed_at IS NULL
   AND p.expires_at>now()
   AND p.channel=p_channel AND p.destination_ref=p_destination_ref
   AND p.secret_ref=p_secret_ref
 RETURNING p.id INTO proof_id;
 IF proof_id IS NULL THEN RETURN false; END IF;
 RETURN sme.approve_asahi_delivery(
    p_digest,p_tenant,p_channel,p_destination_ref,p_secret_ref);
END $body$;

CREATE OR REPLACE FUNCTION sme.revoke_asahi_delivery_stepup(
 p_digest bytea,p_tenant uuid,p_proof uuid
) RETURNS boolean LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,sme AS $body$
DECLARE actor uuid; proof_id uuid;
BEGIN
 IF p_digest IS NULL OR octet_length(p_digest)<>32
    OR p_tenant IS NULL OR p_proof IS NULL THEN RETURN false; END IF;
 SELECT sme.resolve_session(p_digest,p_tenant) INTO actor;
 IF actor IS NULL THEN RETURN false; END IF;
 UPDATE sme.asahi_stepup_proofs p SET consumed_at=now()
 WHERE p.id=p_proof AND p.session_digest=p_digest AND p.tenant_id=p_tenant
   AND p.actor_id=actor AND p.action='revoke' AND p.consumed_at IS NULL
   AND p.expires_at>now()
 RETURNING p.id INTO proof_id;
 IF proof_id IS NULL THEN RETURN false; END IF;
 RETURN sme.revoke_asahi_delivery(p_digest,p_tenant);
END $body$;

-- Remove legacy unguarded public/runtime role capabilities.
REVOKE ALL ON FUNCTION sme.approve_asahi_delivery(bytea,uuid,text,text,text)
 FROM PUBLIC,sme_app,sme_auth,sme_ingest,sme_dispatch,sme_approval,sme_stepup;
REVOKE ALL ON FUNCTION sme.revoke_asahi_delivery(bytea,uuid)
 FROM PUBLIC,sme_app,sme_auth,sme_ingest,sme_dispatch,sme_approval,sme_stepup;
REVOKE ALL ON FUNCTION sme.issue_asahi_stepup(bytea,uuid,text,text,text,text,integer)
 FROM PUBLIC,sme_app,sme_auth,sme_ingest,sme_dispatch,sme_approval;
GRANT EXECUTE ON FUNCTION sme.issue_asahi_stepup(bytea,uuid,text,text,text,text,integer)
 TO sme_stepup;
REVOKE ALL ON FUNCTION sme.approve_asahi_delivery_stepup(bytea,uuid,uuid,text,text,text)
 FROM PUBLIC,sme_app,sme_auth,sme_ingest,sme_dispatch,sme_stepup;
REVOKE ALL ON FUNCTION sme.revoke_asahi_delivery_stepup(bytea,uuid,uuid)
 FROM PUBLIC,sme_app,sme_auth,sme_ingest,sme_dispatch,sme_stepup;
GRANT EXECUTE ON FUNCTION sme.approve_asahi_delivery_stepup(bytea,uuid,uuid,text,text,text)
 TO sme_approval;
GRANT EXECUTE ON FUNCTION sme.revoke_asahi_delivery_stepup(bytea,uuid,uuid)
 TO sme_approval;
COMMIT;
