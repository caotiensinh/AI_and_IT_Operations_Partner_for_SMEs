"""PostgreSQL tests of durable, enrollment-bound polling leases."""
import hashlib
import os
import secrets
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

try:
    import psycopg
except ImportError:
    psycopg=None

DSN=os.getenv("SME_TEST_DATABASE_DSN")
ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(DSN and psycopg,"needs disposable PostgreSQL")
class PollLeaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin=psycopg.connect(DSN,autocommit=True)
        for file in sorted((ROOT/"migrations").glob("*.sql")):
            cls.admin.execute(file.read_text())
    @classmethod
    def tearDownClass(cls):
        cls.admin.close()

    def setUp(self):
        self.tenant,self.site,self.device,self.enrollment=[uuid4() for _ in range(4)]
        self.token=secrets.token_urlsafe(32)
        self.holder,self.other=uuid4(),uuid4()
        self.admin.execute(
            "INSERT INTO sme.tenants(id,slug,display_name) VALUES(%s,%s,'Lease')",
            (self.tenant,"lease-"+self.tenant.hex[:12]))
        self.admin.execute("INSERT INTO sme.sites(tenant_id,id,label) VALUES (%s,%s,'Site')",
                           (self.tenant,self.site))
        self.admin.execute("INSERT INTO sme.assets(tenant_id,id,site_id,name) VALUES (%s,%s,%s,'Node')",
                           (self.tenant,self.device,self.site))
        self.admin.execute(
            "INSERT INTO sme.asahi_enrollments(id,tenant_id,site_id,device_id,credential_digest) "
            "VALUES (%s,%s,%s,%s,%s)",
            (self.enrollment,self.tenant,self.site,self.device,hashlib.sha256(self.token.encode()).digest()))

    def execute(self,name,parameters,role="sme_ingest"):
        with psycopg.connect(DSN) as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE "+role)
                return conn.execute("SELECT sme."+name,parameters).fetchone()[0]

    def claim(self,holder=None,token=None,seconds=30,role="sme_ingest"):
        return self.execute(
            "try_acquire_asahi_poll(%s,%s,%s,%s)",
            (self.enrollment,hashlib.sha256((token or self.token).encode()).digest(),
             holder or self.holder,seconds),role)

    def finish(self,holder=None,success=True):
        return self.execute(
            "complete_asahi_poll(%s,%s,%s,%s,%s,%s)",
            (self.enrollment,hashlib.sha256(self.token.encode()).digest(),
             holder or self.holder,success,60,5))

    def test_first_worker_wins_and_second_denied(self):
        self.assertTrue(self.claim())
        self.assertFalse(self.claim(self.other))
        self.assertTrue(self.finish())
        self.assertFalse(self.claim(self.other))

    def test_expired_lease_can_be_reclaimed(self):
        self.assertTrue(self.claim())
        self.admin.execute(
            "UPDATE sme.asahi_poll_lease SET lease_until=now()-interval '1 second' "
            "WHERE enrollment_id=%s",(self.enrollment,))
        self.assertTrue(self.claim(self.other))
        self.assertFalse(self.finish(self.holder))
        self.assertTrue(self.finish(self.other))

    def test_completion_restricted_to_owner(self):
        self.assertTrue(self.claim())
        self.assertFalse(self.finish(self.other))
        self.assertTrue(self.finish(self.holder))
        self.assertFalse(self.finish(self.holder))

    def test_wrong_credential_rejected(self):
        self.assertFalse(self.claim(token=secrets.token_urlsafe(32)))
        self.assertTrue(self.claim())

    def test_revoked_enrollment_rejected(self):
        self.admin.execute("UPDATE sme.asahi_enrollments SET status='revoked' WHERE id=%s",
                           (self.enrollment,))
        self.assertFalse(self.claim())
        self.assertFalse(self.finish())

    def test_suspended_tenant_rejected(self):
        self.admin.execute("UPDATE sme.tenants SET status='suspended' WHERE id=%s",
                           (self.tenant,))
        self.assertFalse(self.claim())

    def test_bad_lease_duration_rejected(self):
        self.assertFalse(self.claim(seconds=4))
        self.assertFalse(self.claim(seconds=301))
        self.assertTrue(self.claim(seconds=5))

    def test_failure_next_due_is_shorter_than_success(self):
        self.assertTrue(self.claim())
        self.assertTrue(self.finish(success=False))
        delay=self.admin.execute(
            "SELECT extract(epoch FROM(next_due-updated_at)) FROM sme.asahi_poll_lease "
            "WHERE enrollment_id=%s",(self.enrollment,)).fetchone()[0]
        self.assertTrue(4 <= float(delay) <= 6)
        self.assertFalse(self.claim(self.other))

    def test_concurrent_claim_one_winner(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            answers=list(executor.map(self.claim,(self.holder,self.other)))
        self.assertEqual(sorted(answers),[False,True])

    def test_ingest_and_web_cannot_access_lease_table(self):
        for role in ("sme_ingest","sme_app"):
            with self.subTest(role=role),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with self.admin.transaction():
                    self.admin.execute("SET LOCAL ROLE "+role)
                    self.admin.execute("SELECT * FROM sme.asahi_poll_lease").fetchall()

    def test_real_database_lease_tick_ingests_exactly_once(self):
        from datetime import datetime,timezone
        from unittest.mock import Mock
        from sme_partner.adapters.asahi import DeviceBinding,NormalizedTelemetry
        from sme_partner.asahi_ingest import IngestAuthorization
        from sme_partner.asahi_leased_worker import run_leased_ingest_tick
        when=datetime.now(timezone.utc).replace(microsecond=0)
        binding=DeviceBinding(self.tenant,self.site,self.device)
        sample=NormalizedTelemetry(tenant_id=self.tenant,site_id=self.site,
            device_id=self.device,sampled_at=when,hostname='lease-node',
            cpu_percent=27.5,memory_percent=44,uptime_seconds=60,disk_mounts=())
        poller=Mock()
        poller.poll.return_value=sample
        auth=IngestAuthorization(self.enrollment,self.token,binding)
        params=dict(poller=poller,connect=lambda:psycopg.connect(DSN),
                    auth=auth,worker_id=self.holder,observed_at=when)
        self.assertEqual(run_leased_ingest_tick(**params),"inserted")
        self.assertEqual(run_leased_ingest_tick(**params),"not_due")
        poller.poll.assert_called_once_with(when)
        count=self.admin.execute(
            "SELECT count(*) FROM sme.asahi_samples WHERE tenant_id=%s AND device_id=%s AND sampled_at=%s",
            (self.tenant,self.device,when)).fetchone()[0]
        self.assertEqual(count,1)

    def test_poll_error_sets_retry_due_without_inserting_sample(self):
        from datetime import datetime,timezone
        from unittest.mock import Mock
        from sme_partner.adapters.asahi import DeviceBinding
        from sme_partner.asahi_ingest import IngestAuthorization
        from sme_partner.asahi_leased_worker import run_leased_ingest_tick
        poller=Mock()
        poller.poll.side_effect=TimeoutError('offline')
        when=datetime.now(timezone.utc)
        auth=IngestAuthorization(self.enrollment,self.token,
                                 DeviceBinding(self.tenant,self.site,self.device))
        with self.assertRaises(TimeoutError):
            run_leased_ingest_tick(poller=poller,connect=lambda:psycopg.connect(DSN),
                auth=auth,worker_id=self.holder,observed_at=when)
        outcome=self.admin.execute(
            "SELECT last_outcome FROM sme.asahi_poll_lease WHERE enrollment_id=%s",
            (self.enrollment,)).fetchone()[0]
        self.assertEqual(outcome,'retry')

    def test_web_cannot_claim(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.claim(role="sme_app")
