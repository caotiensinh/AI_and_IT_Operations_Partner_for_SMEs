-- M2.14: outbox delivery lease and ack state. Does not send notifications.
BEGIN;
DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='sme_dispatch') THEN
  CREATE ROLE sme_dispatch NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
 END IF;
END $$;
GRANT USAGE ON SCHEMA sme TO sme_dispatch;
ALTER TABLE sme.asahi_alert_outbox
 ADD COLUMN IF NOT EXISTS delivery_owner uuid,
 ADD COLUMN IF NOT EXISTS delivery_lease_until timestamptz,
 ADD COLUMN IF NOT EXISTS delivery_attempts integer NOT NULL DEFAULT 0,
 ADD COLUMN IF NOT EXISTS next_attempt_at timestamptz NOT NULL DEFAULT now(),
 ADD COLUMN IF NOT EXISTS delivered_at timestamptz,
 ADD COLUMN IF NOT EXISTS dead_lettered_at timestamptz;
ALTER TABLE sme.asahi_alert_outbox
 DROP CONSTRAINT IF EXISTS asahi_alert_delivery_attempts_check;
ALTER TABLE sme.asahi_alert_outbox
 ADD CONSTRAINT asahi_alert_delivery_attempts_check
 CHECK(delivery_attempts BETWEEN 0 AND 5);
CREATE INDEX IF NOT EXISTS ix_asahi_outbox_delivery_due
 ON sme.asahi_alert_outbox(next_attempt_at,id)
 WHERE delivered_at IS NULL AND dead_lettered_at IS NULL;
REVOKE ALL ON sme.asahi_alert_outbox FROM PUBLIC,sme_dispatch,sme_app,sme_ingest,sme_auth;

-- Separate dispatcher service role may only claim one message at a time.
-- There are no delivery URLs, external credentials or provider calls in SQL.
CREATE OR REPLACE FUNCTION sme.claim_asahi_alert(
 p_tenant uuid, p_owner uuid, p_lease_seconds integer
) RETURNS TABLE(
 event_id bigint,tenant_id uuid,site_id uuid,device_id uuid,
 metric text,transition text,metric_value numeric,sampled_at timestamptz
)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,sme AS $$
BEGIN
 IF p_tenant IS NULL OR p_owner IS NULL OR p_owner='00000000-0000-0000-0000-000000000000'::uuid
   OR p_lease_seconds IS NULL OR p_lease_seconds NOT BETWEEN 5 AND 300
 THEN RETURN; END IF;
 RETURN QUERY
 WITH candidate AS (
   SELECT o.id FROM sme.asahi_alert_outbox o
   JOIN sme.tenants t ON t.id=o.tenant_id AND t.status='active'
   WHERE o.tenant_id=p_tenant AND o.delivered_at IS NULL AND o.dead_lettered_at IS NULL
     AND o.next_attempt_at<=now() AND o.delivery_attempts<5
     AND (o.delivery_lease_until IS NULL OR o.delivery_lease_until<=now())
   ORDER BY o.next_attempt_at,o.id
   LIMIT 1 FOR UPDATE OF o SKIP LOCKED
 )
 UPDATE sme.asahi_alert_outbox o
 SET delivery_owner=p_owner,
     delivery_lease_until=now()+make_interval(secs=>p_lease_seconds),
     delivery_attempts=o.delivery_attempts+1
 FROM candidate
 WHERE o.id=candidate.id
 RETURNING o.id,o.tenant_id,o.site_id,o.device_id,o.metric,o.transition,
           o.metric_value,o.sampled_at;
END $$;

-- Acknowledgement must match BOTH the event and the current lease owner.
-- 'success' means the caller has confirmed provider delivery; it is never
-- inferred by queue claim. Outbox guarantees at-least-once, not exactly-once.
CREATE OR REPLACE FUNCTION sme.finish_asahi_alert(
 p_id bigint,p_owner uuid,p_success boolean,p_retry_seconds integer
) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,sme AS $$
DECLARE changed bigint;
BEGIN
 IF p_id IS NULL OR p_id<=0 OR p_owner IS NULL
    OR p_owner='00000000-0000-0000-0000-000000000000'::uuid
    OR p_success IS NULL OR p_retry_seconds IS NULL
    OR p_retry_seconds NOT BETWEEN 5 AND 3600
 THEN RETURN false; END IF;
 UPDATE sme.asahi_alert_outbox o
 SET delivery_owner=NULL,delivery_lease_until=NULL,
     delivered_at=CASE WHEN p_success THEN now() ELSE o.delivered_at END,
     dead_lettered_at=CASE WHEN NOT p_success AND o.delivery_attempts>=5
                            THEN now() ELSE o.dead_lettered_at END,
     next_attempt_at=CASE WHEN NOT p_success AND o.delivery_attempts<5
                          THEN now()+make_interval(secs=>p_retry_seconds)
                          ELSE o.next_attempt_at END
 WHERE o.id=p_id AND o.delivery_owner=p_owner
   AND o.delivery_lease_until>now()
   AND o.delivered_at IS NULL AND o.dead_lettered_at IS NULL
 RETURNING o.id INTO changed;
 RETURN changed IS NOT NULL;
END $$;

REVOKE ALL ON FUNCTION sme.claim_asahi_alert(uuid,uuid,integer) FROM PUBLIC,sme_app,sme_auth,sme_ingest;
REVOKE ALL ON FUNCTION sme.finish_asahi_alert(bigint,uuid,boolean,integer) FROM PUBLIC,sme_app,sme_auth,sme_ingest;
GRANT EXECUTE ON FUNCTION sme.claim_asahi_alert(uuid,uuid,integer) TO sme_dispatch;
GRANT EXECUTE ON FUNCTION sme.finish_asahi_alert(bigint,uuid,boolean,integer) TO sme_dispatch;
COMMIT;
