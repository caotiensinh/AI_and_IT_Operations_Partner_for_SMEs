-- OIDC login transactions: schema owner executes, app role NEVER issues sessions.
BEGIN;
DO $$
BEGIN
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='sme_auth') THEN
  CREATE ROLE sme_auth NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
 END IF;
END $$;
GRANT USAGE ON SCHEMA sme TO sme_auth;
CREATE TABLE IF NOT EXISTS sme.pending_oidc_logins (
 state_digest bytea PRIMARY KEY CHECK(octet_length(state_digest)=32),
 browser_digest bytea NOT NULL CHECK(octet_length(browser_digest)=32),
 verifier text NOT NULL CHECK(length(verifier) BETWEEN 43 AND 128),
 nonce text NOT NULL CHECK(length(nonce) BETWEEN 32 AND 128),
 created_at timestamptz NOT NULL DEFAULT now(),
 expires_at timestamptz NOT NULL,
 CHECK(expires_at>created_at AND expires_at<=created_at+interval '10 minutes')
);
REVOKE ALL ON sme.pending_oidc_logins FROM PUBLIC,sme_app,sme_auth;
CREATE OR REPLACE FUNCTION sme.begin_oidc_login(
 p_state bytea,p_browser bytea,p_verifier text,p_nonce text
) RETURNS void LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,sme AS $$
BEGIN
 IF p_state IS NULL OR octet_length(p_state)<>32
  OR p_browser IS NULL OR octet_length(p_browser)<>32
  OR length(p_verifier) NOT BETWEEN 43 AND 128
  OR length(p_nonce) NOT BETWEEN 32 AND 128 THEN
  RAISE EXCEPTION 'invalid login transaction';
 END IF;
 INSERT INTO sme.pending_oidc_logins(state_digest,browser_digest,verifier,nonce,expires_at)
 VALUES(p_state,p_browser,p_verifier,p_nonce,now()+interval '5 minutes');
END $$;
CREATE OR REPLACE FUNCTION sme.consume_oidc_login(p_state bytea,p_browser bytea)
RETURNS TABLE(code_verifier text,expected_nonce text)
LANGUAGE sql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,sme AS $$
 DELETE FROM sme.pending_oidc_logins p
 WHERE p.state_digest=p_state AND p.browser_digest=p_browser
   AND octet_length(p_state)=32 AND octet_length(p_browser)=32
   AND p.expires_at>now()
 RETURNING p.verifier,p.nonce;
$$;
CREATE OR REPLACE FUNCTION sme.issue_oidc_session(
 p_issuer text,p_subject text,p_digest bytea,p_lifetime_seconds integer
) RETURNS boolean LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,sme AS $$
DECLARE found_identity uuid;
BEGIN
 IF p_issuer IS NULL OR p_subject IS NULL OR p_digest IS NULL
   OR octet_length(p_digest)<>32 OR p_lifetime_seconds NOT BETWEEN 60 AND 28800 THEN
  RETURN false;
 END IF;
 SELECT i.id INTO found_identity FROM sme.identities i
 WHERE i.issuer=p_issuer AND i.subject=p_subject
 AND EXISTS (
  SELECT 1 FROM sme.memberships m JOIN sme.tenants t ON t.id=m.tenant_id
  WHERE m.identity_id=i.id AND m.status='active' AND t.status='active'
 ) LIMIT 1;
 IF found_identity IS NULL THEN RETURN false; END IF;
 INSERT INTO sme.sessions(id,identity_id,token_digest,expires_at)
 VALUES(gen_random_uuid(),found_identity,p_digest,now()+make_interval(secs=>p_lifetime_seconds));
 RETURN true;
END $$;
REVOKE ALL ON FUNCTION sme.begin_oidc_login(bytea,bytea,text,text) FROM PUBLIC,sme_app;
REVOKE ALL ON FUNCTION sme.consume_oidc_login(bytea,bytea) FROM PUBLIC,sme_app;
REVOKE ALL ON FUNCTION sme.issue_oidc_session(text,text,bytea,integer) FROM PUBLIC,sme_app;
GRANT EXECUTE ON FUNCTION sme.begin_oidc_login(bytea,bytea,text,text) TO sme_auth;
GRANT EXECUTE ON FUNCTION sme.consume_oidc_login(bytea,bytea) TO sme_auth;
GRANT EXECUTE ON FUNCTION sme.issue_oidc_session(text,text,bytea,integer) TO sme_auth;
COMMIT;
