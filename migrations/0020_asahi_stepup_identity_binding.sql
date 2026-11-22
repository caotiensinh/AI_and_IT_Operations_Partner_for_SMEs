-- Spec 020: trusted issuer/subject lookup for an isolated MFA verifier.
-- Restricted to NOLOGIN sme_stepup; no table read grants and no proof issuance.
BEGIN;
CREATE OR REPLACE FUNCTION sme.resolve_asahi_stepup_identity(
 p_digest bytea,p_tenant uuid
) RETURNS TABLE(issuer text,subject text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,sme AS $body$
 SELECT i.issuer,i.subject
 FROM sme.identities i
 JOIN sme.sessions s ON s.identity_id=i.id
 JOIN sme.memberships m ON m.identity_id=i.id AND m.tenant_id=p_tenant
 JOIN sme.tenants t ON t.id=p_tenant AND t.status='active'
 WHERE p_digest IS NOT NULL AND octet_length(p_digest)=32
   AND p_tenant IS NOT NULL AND s.token_digest=p_digest
   AND s.revoked_at IS NULL AND s.expires_at>now()
   AND m.status='active'
   AND EXISTS (
    SELECT 1 FROM sme.role_assignments r
    WHERE r.tenant_id=p_tenant AND r.identity_id=i.id
      AND r.role='owner' AND r.scope_type='tenant'
   )
 LIMIT 1;
$body$;
REVOKE ALL ON FUNCTION sme.resolve_asahi_stepup_identity(bytea,uuid)
 FROM PUBLIC,sme_app,sme_auth,sme_ingest,sme_dispatch,sme_approval;
GRANT EXECUTE ON FUNCTION sme.resolve_asahi_stepup_identity(bytea,uuid)
 TO sme_stepup;
COMMIT;
