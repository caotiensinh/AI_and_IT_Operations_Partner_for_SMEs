-- M2.10: transactional, durable alert state and unsent outbox.
-- All writes are through an enrollment-authenticated SECURITY DEFINER function.
-- The web and ingest roles cannot edit tables or deliver notifications.
BEGIN;
CREATE TABLE IF NOT EXISTS sme.asahi_alert_state (
 tenant_id uuid NOT NULL,
 site_id uuid NOT NULL,
 device_id uuid NOT NULL,
 metric text NOT NULL CHECK (metric IN ('cpu','memory')),
 last_sampled_at timestamptz,
 breaches smallint NOT NULL DEFAULT 0 CHECK (breaches BETWEEN 0 AND 2),
 active boolean NOT NULL DEFAULT false,
 PRIMARY KEY(tenant_id,device_id,metric),
 FOREIGN KEY(tenant_id,device_id,site_id)
   REFERENCES sme.assets(tenant_id,id,site_id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS sme.asahi_alert_outbox (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 tenant_id uuid NOT NULL,
 site_id uuid NOT NULL,
 device_id uuid NOT NULL,
 metric text NOT NULL CHECK (metric IN ('cpu','memory')),
 transition text NOT NULL CHECK (transition IN ('triggered','cleared')),
 sampled_at timestamptz NOT NULL,
 metric_value numeric(5,2) NOT NULL CHECK(metric_value BETWEEN 0 AND 100),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,device_id,metric,sampled_at,transition),
 FOREIGN KEY(tenant_id,device_id,site_id)
   REFERENCES sme.assets(tenant_id,id,site_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_asahi_alert_outbox_tenant_created
 ON sme.asahi_alert_outbox(tenant_id,created_at DESC);
REVOKE ALL ON sme.asahi_alert_state,sme.asahi_alert_outbox FROM PUBLIC,sme_app,sme_ingest,sme_auth;
ALTER TABLE sme.asahi_alert_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE sme.asahi_alert_state FORCE ROW LEVEL SECURITY;
ALTER TABLE sme.asahi_alert_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE sme.asahi_alert_outbox FORCE ROW LEVEL SECURITY;

-- No role is granted direct table access; the function resolves enrollment
-- and uses only the existing persisted measurement, never caller-supplied values.
CREATE OR REPLACE FUNCTION sme.evaluate_asahi_alert(
 p_enrollment uuid,
 p_credential_digest bytea,
 p_sampled_at timestamptz
) RETURNS integer
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,sme AS $$
DECLARE
 e record;
 sm record;
 metric_name text;
 metric_value numeric;
 row_state record;
 change_type text;
 event_count integer := 0;
BEGIN
 IF p_enrollment IS NULL OR p_credential_digest IS NULL
    OR octet_length(p_credential_digest)<>32 OR p_sampled_at IS NULL
 THEN RETURN 0; END IF;
 SELECT en.tenant_id,en.site_id,en.device_id INTO e
 FROM sme.asahi_enrollments en
 JOIN sme.tenants t ON t.id=en.tenant_id AND t.status='active'
 WHERE en.id=p_enrollment AND en.status='active'
   AND en.credential_digest=p_credential_digest;
 IF NOT FOUND THEN RETURN 0; END IF;
 PERFORM set_config('sme.tenant_id',e.tenant_id::text,true);
 SELECT cpu_percent,memory_percent INTO sm
 FROM sme.asahi_samples
 WHERE tenant_id=e.tenant_id AND site_id=e.site_id
   AND device_id=e.device_id AND sampled_at=p_sampled_at;
 IF NOT FOUND THEN RETURN 0; END IF;
 FOR metric_name, metric_value IN
    SELECT 'cpu', sm.cpu_percent UNION ALL
    SELECT 'memory', sm.memory_percent
 LOOP
   IF metric_value IS NULL THEN CONTINUE; END IF;
   INSERT INTO sme.asahi_alert_state
      (tenant_id,site_id,device_id,metric)
   VALUES(e.tenant_id,e.site_id,e.device_id,metric_name)
   ON CONFLICT (tenant_id,device_id,metric) DO NOTHING;
   SELECT last_sampled_at,breaches,active INTO row_state
   FROM sme.asahi_alert_state
   WHERE tenant_id=e.tenant_id AND device_id=e.device_id
     AND metric=metric_name FOR UPDATE;
   IF row_state.last_sampled_at IS NOT NULL
      AND p_sampled_at<=row_state.last_sampled_at THEN CONTINUE; END IF;
   change_type:=NULL;
   IF row_state.active THEN
     IF metric_value<=80 THEN
       change_type:='cleared';
       UPDATE sme.asahi_alert_state
       SET last_sampled_at=p_sampled_at,active=false,breaches=0
       WHERE tenant_id=e.tenant_id AND device_id=e.device_id AND metric=metric_name;
     ELSE
       UPDATE sme.asahi_alert_state SET last_sampled_at=p_sampled_at
       WHERE tenant_id=e.tenant_id AND device_id=e.device_id AND metric=metric_name;
     END IF;
   ELSIF metric_value>=90 THEN
     IF row_state.breaches>=1 THEN
       change_type:='triggered';
       UPDATE sme.asahi_alert_state
       SET last_sampled_at=p_sampled_at,active=true,breaches=2
       WHERE tenant_id=e.tenant_id AND device_id=e.device_id AND metric=metric_name;
     ELSE
       UPDATE sme.asahi_alert_state
       SET last_sampled_at=p_sampled_at,breaches=1
       WHERE tenant_id=e.tenant_id AND device_id=e.device_id AND metric=metric_name;
     END IF;
   ELSE
     UPDATE sme.asahi_alert_state
     SET last_sampled_at=p_sampled_at,breaches=0
     WHERE tenant_id=e.tenant_id AND device_id=e.device_id AND metric=metric_name;
   END IF;
   IF change_type IS NOT NULL THEN
     INSERT INTO sme.asahi_alert_outbox
       (tenant_id,site_id,device_id,metric,transition,sampled_at,metric_value)
     VALUES (e.tenant_id,e.site_id,e.device_id,metric_name,change_type,
             p_sampled_at,metric_value)
     ON CONFLICT (tenant_id,device_id,metric,sampled_at,transition)
       DO NOTHING;
     event_count:=event_count+1;
   END IF;
 END LOOP;
 RETURN event_count;
END $$;
REVOKE ALL ON FUNCTION sme.evaluate_asahi_alert(uuid,bytea,timestamptz)
 FROM PUBLIC,sme_app,sme_auth;
GRANT EXECUTE ON FUNCTION sme.evaluate_asahi_alert(uuid,bytea,timestamptz)
 TO sme_ingest;
COMMIT;
