-- Spec 021: PostgreSQL single-use browser/session/action-bound OIDC step-up challenge.
-- These functions do not verify IdP MFA, exchange OAuth tokens, or issue proofs.
BEGIN;
CREATE TABLE IF NOT EXISTS sme.asahi_stepup_challenges (
 state_digest bytea PRIMARY KEY CHECK(octet_length(state_digest)=32),
 browser_digest bytea NOT NULL CHECK(octet_length(browser_digest)=32),
 session_digest bytea NOT NULL CHECK(octet_length(session_digest)=32),
 tenant_id uuid NOT NULL REFERENCES sme.tenants(id),
 action text NOT NULL CHECK(action IN ('approve','revoke')),
 channel text,
 destination_ref text,
 secret_ref text,
 code_verifier text NOT NULL CHECK(code_verifier ~ '^[A-Za-z0-9_-]{64}$'),
 expected_nonce text NOT NULL CHECK(expected_nonce ~ '^[A-Za-z0-9_-]{43}$'),
 created_at timestamptz NOT NULL DEFAULT now(),
 expires_at timestamptz NOT NULL,
 CHECK(expires_at>created_at AND expires_at<=created_at+interval '5 minutes'),
 CHECK(
  (action='revoke' AND channel IS NULL AND destination_ref IS NULL AND secret_ref IS NULL)
  OR (action='approve' AND channel IN ('email','webhook')
       AND destination_ref ~ '^[A-Za-z0-9_./-]{1,128}$'
       AND secret_ref ~ '^[A-Za-z0-9_./-]{1,128}$'
       AND destination_ref !~ '(^|/)[.][.](/|$)'
       AND secret_ref !~ '(^|/)[.][.](/|$)'
       AND left(destination_ref,1)<>'/' AND left(secret_ref,1)<>'/')
 )
);
CREATE INDEX IF NOT EXISTS ix_asahi_stepup_challenge_expiry
 ON sme.asahi_stepup_challenges(expires_at);
REVOKE ALL ON sme.asahi_stepup_challenges
 FROM PUBLIC,sme_app,sme_auth,sme_ingest,sme_dispatch,sme_approval,sme_stepup;
ALTER TABLE sme.asahi_stepup_challenges ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION sme.begin_asahi_stepup_challenge(
 p_state bytea,p_browser bytea,p_digest bytea,p_tenant uuid,
 p_action text,p_channel text,p_destination_ref text,p_secret_ref text,
 p_verifier text,p_nonce text
) RETURNS boolean LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,sme AS $body$
BEGIN
 IF p_state IS NULL OR octet_length(p_state)<>32
    OR p_browser IS NULL OR octet_length(p_browser)<>32
    OR p_digest IS NULL OR octet_length(p_digest)<>32 OR p_tenant IS NULL
    OR p_verifier IS NULL OR p_verifier !~ '^[A-Za-z0-9_-]{64}$'
    OR p_nonce IS NULL OR p_nonce !~ '^[A-Za-z0-9_-]{43}$'
    OR p_action IS NULL OR p_action NOT IN ('approve','revoke')
 THEN RETURN false; END IF;
 IF p_action='approve' AND (
    p_channel IS NULL OR p_channel NOT IN ('email','webhook')
    OR p_destination_ref IS NULL OR p_secret_ref IS NULL
    OR p_destination_ref !~ '^[A-Za-z0-9_./-]{1,128}$'
    OR p_secret_ref !~ '^[A-Za-z0-9_./-]{1,128}$'
    OR p_destination_ref ~ '(^|/)[.][.](/|$)'
    OR p_secret_ref ~ '(^|/)[.][.](/|$)'
    OR left(p_destination_ref,1)='/' OR left(p_secret_ref,1)='/'
 ) THEN RETURN false; END IF;
 IF p_action='revoke' AND (
   p_channel IS NOT NULL OR p_destination_ref IS NOT NULL OR p_secret_ref IS NOT NULL
 ) THEN RETURN false; END IF;
 IF NOT EXISTS (
   SELECT 1 FROM sme.resolve_asahi_stepup_identity(p_digest,p_tenant)
 ) THEN RETURN false; END IF;
 INSERT INTO sme.asahi_stepup_challenges(
   state_digest,browser_digest,session_digest,tenant_id,action,channel,
   destination_ref,secret_ref,code_verifier,expected_nonce,expires_at
 ) VALUES(
   p_state,p_browser,p_digest,p_tenant,p_action,p_channel,
   p_destination_ref,p_secret_ref,p_verifier,p_nonce,now()+interval '5 minutes'
 );
 RETURN true;
END $body$;

CREATE OR REPLACE FUNCTION sme.consume_asahi_stepup_challenge(
 p_state bytea,p_browser bytea,p_digest bytea,p_tenant uuid,
 p_action text,p_channel text,p_destination_ref text,p_secret_ref text
) RETURNS TABLE(code_verifier text,expected_nonce text)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,sme AS $body$
BEGIN
 IF p_state IS NULL OR octet_length(p_state)<>32
    OR p_browser IS NULL OR octet_length(p_browser)<>32
    OR p_digest IS NULL OR octet_length(p_digest)<>32 OR p_tenant IS NULL
    OR NOT EXISTS (
     SELECT 1 FROM sme.resolve_asahi_stepup_identity(p_digest,p_tenant)
    ) THEN RETURN; END IF;
 RETURN QUERY
 DELETE FROM sme.asahi_stepup_challenges c
 WHERE c.state_digest=p_state AND c.browser_digest=p_browser
   AND c.session_digest=p_digest AND c.tenant_id=p_tenant
   AND c.action=p_action
   AND c.channel IS NOT DISTINCT FROM p_channel
   AND c.destination_ref IS NOT DISTINCT FROM p_destination_ref
   AND c.secret_ref IS NOT DISTINCT FROM p_secret_ref
   AND c.expires_at>now()
 RETURNING c.code_verifier,c.expected_nonce;
END $body$;

REVOKE ALL ON FUNCTION sme.begin_asahi_stepup_challenge(
 bytea,bytea,bytea,uuid,text,text,text,text,text,text)
 FROM PUBLIC,sme_app,sme_auth,sme_ingest,sme_dispatch,sme_approval;
REVOKE ALL ON FUNCTION sme.consume_asahi_stepup_challenge(
 bytea,bytea,bytea,uuid,text,text,text,text)
 FROM PUBLIC,sme_app,sme_auth,sme_ingest,sme_dispatch,sme_approval;
GRANT EXECUTE ON FUNCTION sme.begin_asahi_stepup_challenge(
 bytea,bytea,bytea,uuid,text,text,text,text,text,text) TO sme_stepup;
GRANT EXECUTE ON FUNCTION sme.consume_asahi_stepup_challenge(
 bytea,bytea,bytea,uuid,text,text,text,text) TO sme_stepup;
COMMIT;
