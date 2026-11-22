-- Integrated staging canonical migration 0026 (main 0001-0019, Discovery 0020-0026).
-- Browser BFF tenant selector: server-verified session, no user-provided tenant grants.
BEGIN;
CREATE OR REPLACE FUNCTION sme.list_browser_session_tenants(p_digest bytea)
RETURNS TABLE(tenant_id uuid,tenant_label text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,sme
AS $$
 SELECT t.id,t.display_name
 FROM sme.sessions s
 JOIN sme.memberships m ON m.identity_id=s.identity_id
 JOIN sme.tenants t ON t.id=m.tenant_id
 WHERE p_digest IS NOT NULL AND octet_length(p_digest)=32
   AND s.token_digest=p_digest
   AND s.revoked_at IS NULL AND s.expires_at>now()
   AND m.status='active' AND t.status='active'
 ORDER BY t.display_name,t.id
 LIMIT 101;
$$;
REVOKE ALL ON FUNCTION sme.list_browser_session_tenants(bytea) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION sme.list_browser_session_tenants(bytea) TO sme_app;
COMMIT;
