-- M1 security hardening: verify session state before issuing a CSRF token.
BEGIN;
CREATE OR REPLACE FUNCTION sme.session_is_active(p_digest bytea)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,sme AS $$
 SELECT EXISTS (
   SELECT 1 FROM sme.sessions s
   JOIN sme.identities i ON i.id=s.identity_id
   WHERE p_digest IS NOT NULL AND octet_length(p_digest)=32
     AND s.token_digest=p_digest AND s.revoked_at IS NULL AND s.expires_at>now()
     AND EXISTS (
       SELECT 1 FROM sme.memberships m
       JOIN sme.tenants t ON t.id=m.tenant_id
       WHERE m.identity_id=i.id AND m.status='active' AND t.status='active'
     )
 );
$$;
REVOKE ALL ON FUNCTION sme.session_is_active(bytea) FROM PUBLIC,sme_auth;
GRANT EXECUTE ON FUNCTION sme.session_is_active(bytea) TO sme_app;
COMMIT;
