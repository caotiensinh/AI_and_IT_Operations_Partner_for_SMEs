-- Opaque first-party session storage. Execute as migration/provisioning owner.
-- Runtime sme_app receives EXECUTE on narrowly scoped SECURITY DEFINER functions,
-- not direct read/write access to session secrets or global identity/membership data.
BEGIN;
CREATE TABLE IF NOT EXISTS sme.sessions (
 id uuid PRIMARY KEY,
 identity_id uuid NOT NULL REFERENCES sme.identities(id) ON DELETE RESTRICT,
 token_digest bytea NOT NULL UNIQUE CHECK(octet_length(token_digest)=32),
 created_at timestamptz NOT NULL DEFAULT now(),
 expires_at timestamptz NOT NULL CHECK(expires_at>created_at),
 revoked_at timestamptz,
 CHECK (revoked_at IS NULL OR revoked_at>=created_at)
);
CREATE INDEX IF NOT EXISTS sessions_identity_idx ON sme.sessions(identity_id,expires_at);
REVOKE ALL ON sme.sessions FROM PUBLIC;
REVOKE ALL ON sme.sessions FROM sme_app;
CREATE OR REPLACE FUNCTION sme.resolve_session(p_digest bytea,p_tenant uuid)
RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,sme
AS $$
 SELECT s.identity_id
 FROM sme.sessions s
 JOIN sme.memberships m ON m.identity_id=s.identity_id AND m.tenant_id=p_tenant
 JOIN sme.tenants t ON t.id=p_tenant
 WHERE s.token_digest=p_digest AND octet_length(p_digest)=32
   AND s.revoked_at IS NULL AND s.expires_at>now()
   AND m.status='active' AND t.status='active'
 LIMIT 1;
$$;
CREATE OR REPLACE FUNCTION sme.revoke_session(p_digest bytea)
RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,sme
AS $$
DECLARE affected integer;
BEGIN
 IF p_digest IS NULL OR octet_length(p_digest)<>32 THEN RETURN false; END IF;
 UPDATE sme.sessions
 SET revoked_at=now()
 WHERE token_digest=p_digest AND revoked_at IS NULL AND expires_at>now();
 GET DIAGNOSTICS affected=ROW_COUNT;
 RETURN affected=1;
END $$;
REVOKE ALL ON FUNCTION sme.resolve_session(bytea,uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION sme.revoke_session(bytea) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION sme.resolve_session(bytea,uuid) TO sme_app;
GRANT EXECUTE ON FUNCTION sme.revoke_session(bytea) TO sme_app;
-- No session issuance rights granted to the runtime role.
COMMIT;
