-- Spec 023: read only server-bound action for OAuth callback; never trust callback query payload.
BEGIN;
CREATE OR REPLACE FUNCTION sme.lookup_asahi_stepup_challenge(
 p_state bytea,p_browser bytea,p_digest bytea
) RETURNS TABLE(tenant_id uuid,action text,channel text,destination_ref text,secret_ref text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,sme AS $body$
 SELECT c.tenant_id,c.action,c.channel,c.destination_ref,c.secret_ref
 FROM sme.asahi_stepup_challenges c
 WHERE p_state IS NOT NULL AND octet_length(p_state)=32
   AND p_browser IS NOT NULL AND octet_length(p_browser)=32
   AND p_digest IS NOT NULL AND octet_length(p_digest)=32
   AND c.state_digest=p_state AND c.browser_digest=p_browser
   AND c.session_digest=p_digest AND c.expires_at>now()
   AND EXISTS (
      SELECT 1 FROM sme.resolve_asahi_stepup_identity(p_digest,c.tenant_id)
   )
 LIMIT 1;
$body$;
REVOKE ALL ON FUNCTION sme.lookup_asahi_stepup_challenge(bytea,bytea,bytea)
 FROM PUBLIC,sme_app,sme_auth,sme_ingest,sme_dispatch,sme_approval;
GRANT EXECUTE ON FUNCTION sme.lookup_asahi_stepup_challenge(bytea,bytea,bytea)
 TO sme_stepup;
COMMIT;
