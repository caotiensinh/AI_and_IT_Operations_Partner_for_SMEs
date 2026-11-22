-- M2.12: durable per-enrollment polling leases, not an enabled scheduler.
BEGIN;
CREATE TABLE IF NOT EXISTS sme.asahi_poll_lease (
 enrollment_id uuid PRIMARY KEY REFERENCES sme.asahi_enrollments(id) ON DELETE RESTRICT,
 tenant_id uuid NOT NULL,
 device_id uuid NOT NULL,
 lease_owner uuid NOT NULL,
 lease_until timestamptz NOT NULL,
 next_due timestamptz NOT NULL,
 last_outcome text CHECK(last_outcome IN ('success','retry')),
 updated_at timestamptz NOT NULL DEFAULT now()
);
REVOKE ALL ON sme.asahi_poll_lease FROM PUBLIC,sme_app,sme_auth,sme_ingest;
ALTER TABLE sme.asahi_poll_lease ENABLE ROW LEVEL SECURITY;
ALTER TABLE sme.asahi_poll_lease FORCE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION sme.try_acquire_asahi_poll(
 p_enrollment uuid,p_digest bytea,p_worker uuid,p_lease_seconds integer
) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,sme AS $$
DECLARE e record;
DECLARE acquired uuid;
BEGIN
 IF p_enrollment IS NULL OR p_digest IS NULL OR octet_length(p_digest)<>32
   OR p_worker IS NULL OR p_worker='00000000-0000-0000-0000-000000000000'::uuid
   OR p_lease_seconds IS NULL OR p_lease_seconds NOT BETWEEN 5 AND 300
 THEN RETURN false; END IF;
 SELECT en.id,en.tenant_id,en.device_id INTO e
 FROM sme.asahi_enrollments en
 JOIN sme.tenants t ON t.id=en.tenant_id AND t.status='active'
 WHERE en.id=p_enrollment AND en.status='active'
 AND en.credential_digest=p_digest;
 IF NOT FOUND THEN RETURN false; END IF;
 PERFORM set_config('sme.tenant_id',e.tenant_id::text,true);
 INSERT INTO sme.asahi_poll_lease(enrollment_id,tenant_id,device_id,lease_owner,lease_until,next_due)
 VALUES(e.id,e.tenant_id,e.device_id,p_worker,
        now()+make_interval(secs=>p_lease_seconds),now())
 ON CONFLICT(enrollment_id) DO UPDATE
 SET lease_owner=EXCLUDED.lease_owner,lease_until=EXCLUDED.lease_until,
     updated_at=now()
 WHERE sme.asahi_poll_lease.lease_until<=now()
   AND sme.asahi_poll_lease.next_due<=now()
 RETURNING enrollment_id INTO acquired;
 RETURN acquired IS NOT NULL;
END $$;

CREATE OR REPLACE FUNCTION sme.complete_asahi_poll(
 p_enrollment uuid,p_digest bytea,p_worker uuid,p_success boolean,
 p_interval_seconds integer,p_retry_seconds integer
) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,sme AS $$
DECLARE e record;
DECLARE changed uuid;
BEGIN
 IF p_enrollment IS NULL OR p_digest IS NULL OR octet_length(p_digest)<>32
    OR p_worker IS NULL OR p_success IS NULL
    OR p_interval_seconds IS NULL OR p_interval_seconds NOT BETWEEN 10 AND 3600
    OR p_retry_seconds IS NULL OR p_retry_seconds NOT BETWEEN 1 AND 300
 THEN RETURN false; END IF;
 SELECT en.id,en.tenant_id INTO e FROM sme.asahi_enrollments en
 JOIN sme.tenants t ON t.id=en.tenant_id AND t.status='active'
 WHERE en.id=p_enrollment AND en.credential_digest=p_digest AND en.status='active';
 IF NOT FOUND THEN RETURN false; END IF;
 PERFORM set_config('sme.tenant_id',e.tenant_id::text,true);
 UPDATE sme.asahi_poll_lease
 SET lease_until=now(),
     next_due=now()+make_interval(secs=>
                 CASE WHEN p_success THEN p_interval_seconds ELSE p_retry_seconds END),
     last_outcome=CASE WHEN p_success THEN 'success' ELSE 'retry' END,
     updated_at=now()
 WHERE enrollment_id=p_enrollment AND tenant_id=e.tenant_id
   AND lease_owner=p_worker AND lease_until>now()
 RETURNING enrollment_id INTO changed;
 RETURN changed IS NOT NULL;
END $$;
REVOKE ALL ON FUNCTION sme.try_acquire_asahi_poll(uuid,bytea,uuid,integer)
 FROM PUBLIC,sme_app,sme_auth;
REVOKE ALL ON FUNCTION sme.complete_asahi_poll(uuid,bytea,uuid,boolean,integer,integer)
 FROM PUBLIC,sme_app,sme_auth;
GRANT EXECUTE ON FUNCTION sme.try_acquire_asahi_poll(uuid,bytea,uuid,integer) TO sme_ingest;
GRANT EXECUTE ON FUNCTION sme.complete_asahi_poll(uuid,bytea,uuid,boolean,integer,integer) TO sme_ingest;
COMMIT;
