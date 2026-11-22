-- Spec 016: offline tenant-approved routing store; no external delivery.
-- Run only under the migration owner. Application, ingest, auth and dispatch
-- roles cannot configure destinations or read the underlying tables.
BEGIN;
CREATE TABLE IF NOT EXISTS sme.asahi_delivery_destinations (
 tenant_id uuid PRIMARY KEY REFERENCES sme.tenants(id) ON DELETE RESTRICT,
 channel text NOT NULL CHECK (channel IN ('email','webhook')),
 destination_ref text NOT NULL,
 secret_ref text NOT NULL,
 enabled boolean NOT NULL DEFAULT false,
 approved_by uuid NOT NULL,
 approved_at timestamptz NOT NULL DEFAULT now(),
 revoked_at timestamptz,
 FOREIGN KEY (tenant_id,approved_by)
   REFERENCES sme.memberships(tenant_id,identity_id) ON DELETE RESTRICT,
 CONSTRAINT asahi_destination_ref_safe CHECK (
    destination_ref ~ '^[A-Za-z0-9_./-]{1,128}$'
    AND destination_ref !~ '(^|/)[.][.](/|$)'
    AND left(destination_ref,1)<>'/'
 ),
 CONSTRAINT asahi_secret_ref_safe CHECK (
    secret_ref ~ '^[A-Za-z0-9_./-]{1,128}$'
    AND secret_ref !~ '(^|/)[.][.](/|$)'
    AND left(secret_ref,1)<>'/'
 ),
 CONSTRAINT asahi_delivery_enabled_not_revoked CHECK (NOT enabled OR revoked_at IS NULL)
);
CREATE TABLE IF NOT EXISTS sme.asahi_delivery_policy_audit (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES sme.tenants(id) ON DELETE RESTRICT,
 actor_id uuid NOT NULL REFERENCES sme.identities(id) ON DELETE RESTRICT,
 operation text NOT NULL CHECK (operation IN ('created','updated','revoked')),
 previous_enabled boolean,
 current_enabled boolean NOT NULL,
 occurred_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
REVOKE ALL ON sme.asahi_delivery_destinations,
 sme.asahi_delivery_policy_audit FROM PUBLIC,sme_app,sme_auth,sme_ingest,sme_dispatch;
REVOKE ALL ON SEQUENCE sme.asahi_delivery_policy_audit_id_seq
 FROM PUBLIC,sme_app,sme_auth,sme_ingest,sme_dispatch;
ALTER TABLE sme.asahi_delivery_destinations ENABLE ROW LEVEL SECURITY;
ALTER TABLE sme.asahi_delivery_policy_audit ENABLE ROW LEVEL SECURITY;
-- No RLS policy for any runtime role. Migration owner is the sole provisioning
-- authority pending a separately reviewed authenticated owner approval workflow.
CREATE OR REPLACE FUNCTION sme.audit_asahi_delivery_policy()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,sme AS $$
BEGIN
 IF TG_OP='DELETE' THEN
   RAISE EXCEPTION 'delivery policies must be revoked, not deleted';
 END IF;
 IF TG_OP='UPDATE' AND NEW.tenant_id<>OLD.tenant_id THEN
   RAISE EXCEPTION 'cannot move policy between tenants';
 END IF;
 INSERT INTO sme.asahi_delivery_policy_audit(
   tenant_id,actor_id,operation,previous_enabled,current_enabled
 ) VALUES (
   NEW.tenant_id,NEW.approved_by,
   CASE WHEN TG_OP='INSERT' THEN 'created'
        WHEN NEW.revoked_at IS NOT NULL AND OLD.revoked_at IS NULL THEN 'revoked'
        ELSE 'updated' END,
   CASE WHEN TG_OP='INSERT' THEN NULL ELSE OLD.enabled END,
   NEW.enabled
 );
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION sme.audit_asahi_delivery_policy() FROM PUBLIC;
DROP TRIGGER IF EXISTS trg_asahi_delivery_policy_audit
 ON sme.asahi_delivery_destinations;
CREATE TRIGGER trg_asahi_delivery_policy_audit
 BEFORE INSERT OR UPDATE OR DELETE ON sme.asahi_delivery_destinations
 FOR EACH ROW EXECUTE FUNCTION sme.audit_asahi_delivery_policy();

-- Called only by a restricted dispatcher holding an unexpired lease.
-- The event's persisted tenant is authoritative; no tenant argument exists.
CREATE OR REPLACE FUNCTION sme.resolve_asahi_delivery(
 p_event_id bigint,p_lease_owner uuid
) RETURNS TABLE(
 tenant_id uuid,channel text,destination_ref text,secret_ref text,
 idempotency_key text
)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,sme AS $$
 SELECT o.tenant_id,d.channel,d.destination_ref,d.secret_ref,o.id::text
 FROM sme.asahi_alert_outbox o
 JOIN sme.tenants t ON t.id=o.tenant_id AND t.status='active'
 JOIN sme.asahi_delivery_destinations d ON d.tenant_id=o.tenant_id
 WHERE o.id=p_event_id AND p_event_id>0
   AND p_lease_owner IS NOT NULL
   AND p_lease_owner<>'00000000-0000-0000-0000-000000000000'::uuid
   AND o.delivery_owner=p_lease_owner
   AND o.delivery_lease_until>now()
   AND o.delivered_at IS NULL AND o.dead_lettered_at IS NULL
   AND d.enabled=true AND d.revoked_at IS NULL
$$;
REVOKE ALL ON FUNCTION sme.resolve_asahi_delivery(bigint,uuid)
 FROM PUBLIC,sme_app,sme_auth,sme_ingest;
GRANT EXECUTE ON FUNCTION sme.resolve_asahi_delivery(bigint,uuid)
 TO sme_dispatch;
COMMIT;
