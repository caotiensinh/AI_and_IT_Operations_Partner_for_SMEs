-- Tenant selector API: only active memberships belonging to an active session.
BEGIN;
CREATE OR REPLACE FUNCTION sme.list_session_tenants(p_digest bytea)
RETURNS TABLE(tenant_id uuid,display_name text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,sme AS $$
 SELECT t.id,t.display_name
 FROM sme.sessions s
 JOIN sme.memberships m ON m.identity_id=s.identity_id AND m.status='active'
 JOIN sme.tenants t ON t.id=m.tenant_id AND t.status='active'
 WHERE s.token_digest=p_digest AND octet_length(p_digest)=32
   AND s.revoked_at IS NULL AND s.expires_at>now()
 ORDER BY t.display_name,t.id;
$$;
REVOKE ALL ON FUNCTION sme.list_session_tenants(bytea) FROM PUBLIC,sme_auth;
GRANT EXECUTE ON FUNCTION sme.list_session_tenants(bytea) TO sme_app;
COMMIT;
