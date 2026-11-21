"""Real PostgreSQL 16 credential isolation and idempotent ingest tests."""
import hashlib
import os
import secrets
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from uuid import uuid4
from unittest.mock import Mock
try:
    import psycopg
    from sme_partner.asahi_ingest import IngestAuthorization,ingest_one
    from sme_partner.adapters.asahi import DeviceBinding,NormalizedTelemetry
except ImportError:
    psycopg=None

DSN=os.getenv("SME_TEST_DATABASE_DSN")
ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(DSN and psycopg,"Requires disposable PostgreSQL")
class AsahiTrustedIngestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db=psycopg.connect(DSN,autocommit=True)
        for path in sorted((ROOT/"migrations").glob("*.sql")):
            cls.db.execute(path.read_text())
        cls.a,cls.b,cls.site_a,cls.site_b,cls.device_a,cls.device_b,cls.enroll_a,cls.enroll_b=[uuid4() for _ in range(8)]
        cls.token_a=secrets.token_urlsafe(32)
        cls.token_b=secrets.token_urlsafe(32)
        cls.now=datetime.now(timezone.utc).replace(microsecond=0)
        cls.db.execute(
            "INSERT INTO sme.tenants(id,slug,display_name) VALUES (%s,%s,'Enrolled A'),(%s,%s,'Enrolled B')",
            (cls.a,'ingest-'+cls.a.hex[:12],cls.b,'ingest-'+cls.b.hex[:12]))
        cls.db.execute(
            "INSERT INTO sme.sites(tenant_id,id,label) VALUES (%s,%s,'A'),(%s,%s,'B')",
            (cls.a,cls.site_a,cls.b,cls.site_b))
        cls.db.execute(
            "INSERT INTO sme.assets(tenant_id,id,site_id,name) VALUES (%s,%s,%s,'A'),(%s,%s,%s,'B')",
            (cls.a,cls.device_a,cls.site_a,cls.b,cls.device_b,cls.site_b))
        for eid,tenant,site,device,token in (
            (cls.enroll_a,cls.a,cls.site_a,cls.device_a,cls.token_a),
            (cls.enroll_b,cls.b,cls.site_b,cls.device_b,cls.token_b),
        ):
            cls.db.execute(
                "INSERT INTO sme.asahi_enrollments(id,tenant_id,site_id,device_id,credential_digest) "
                "VALUES (%s,%s,%s,%s,%s)",
                (eid,tenant,site,device,hashlib.sha256(token.encode()).digest()))
    @classmethod
    def tearDownClass(cls):
        cls.db.close()
    def call(self,eid,token,stamp=None):
        with self.db.transaction():
            self.db.execute("SET LOCAL ROLE sme_ingest")
            return self.db.execute(
                "SELECT sme.ingest_asahi_sample(%s,%s,%s,%s,%s::numeric,%s::numeric,%s::bigint)",
                (eid,hashlib.sha256(token.encode()).digest(),stamp or self.now,
                 'test-node',43.5,61.0,100),
            ).fetchone()[0]
    def test_positive_and_duplicate(self):
        stamp=self.now+timedelta(seconds=1)
        self.assertTrue(self.call(self.enroll_a,self.token_a,stamp))
        self.assertFalse(self.call(self.enroll_a,self.token_a,stamp))
        row=self.db.execute(
            "SELECT tenant_id,site_id,device_id FROM sme.asahi_samples "
            "WHERE tenant_id=%s AND sampled_at=%s",(self.a,stamp)).fetchone()
        self.assertEqual(row,(self.a,self.site_a,self.device_a))
    def test_credential_cannot_cross_enrollment(self):
        self.assertFalse(self.call(self.enroll_b,self.token_a,self.now+timedelta(seconds=2)))
        self.assertFalse(self.call(uuid4(),self.token_a,self.now+timedelta(seconds=2)))
    def test_revocation_blocks_new_samples(self):
        self.db.execute("UPDATE sme.asahi_enrollments SET status='revoked' WHERE id=%s",(self.enroll_a,))
        try:
            self.assertFalse(self.call(self.enroll_a,self.token_a,self.now+timedelta(seconds=3)))
        finally:
            self.db.execute("UPDATE sme.asahi_enrollments SET status='active' WHERE id=%s",(self.enroll_a,))
    def test_suspended_tenant_blocks_new_samples(self):
        self.db.execute("UPDATE sme.tenants SET status='suspended' WHERE id=%s",(self.b,))
        try:
            self.assertFalse(self.call(self.enroll_b,self.token_b,self.now+timedelta(seconds=3)))
        finally:
            self.db.execute("UPDATE sme.tenants SET status='active' WHERE id=%s",(self.b,))
    def test_stale_or_future_samples_rejected(self):
        self.assertFalse(self.call(self.enroll_b,self.token_b,self.now-timedelta(minutes=7)))
        self.assertFalse(self.call(self.enroll_b,self.token_b,self.now+timedelta(minutes=7)))
    def test_mismatched_site_enrollment_fk_rejected(self):
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            self.db.execute(
                "INSERT INTO sme.asahi_enrollments(id,tenant_id,site_id,device_id,credential_digest) "
                "VALUES (%s,%s,%s,%s,%s)",
                (uuid4(),self.a,self.site_b,self.device_b,b'1'*32))
    def test_ingest_role_cannot_read_credentials(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.db.transaction():
                self.db.execute("SET LOCAL ROLE sme_ingest")
                self.db.execute("SELECT credential_digest FROM sme.asahi_enrollments").fetchall()
    def test_ingest_role_cannot_direct_write(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.db.transaction():
                self.db.execute("SET LOCAL ROLE sme_ingest")
                self.db.execute(
                    "INSERT INTO sme.asahi_samples(tenant_id,device_id,site_id,sampled_at,hostname) "
                    "VALUES (%s,%s,%s,%s,'forged')",
                    (self.a,self.device_a,self.site_a,self.now+timedelta(seconds=4)))
    def test_web_runtime_cannot_call_ingest(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.db.transaction():
                self.db.execute("SET LOCAL ROLE sme_app")
                self.db.execute("SELECT sme.ingest_asahi_sample(%s,%s,%s,'x',20::numeric,30::numeric,20::bigint)",
                                (self.enroll_a,hashlib.sha256(self.token_a.encode()).digest(),self.now))
    def test_duplicate_device_enrollment_denied(self):
        with self.assertRaises(psycopg.errors.UniqueViolation):
            self.db.execute(
                "INSERT INTO sme.asahi_enrollments(id,tenant_id,site_id,device_id,credential_digest) "
                "VALUES (%s,%s,%s,%s,%s)",
                (uuid4(),self.a,self.site_a,self.device_a,hashlib.sha256(b'new').digest()))
    def test_worker_uses_trusted_binding(self):
        sample=NormalizedTelemetry(
            tenant_id=self.a,site_id=self.site_a,device_id=self.device_a,
            sampled_at=self.now+timedelta(seconds=5),hostname='worker-node',
            cpu_percent=44.0,memory_percent=55.0,uptime_seconds=600,disk_mounts=()
        )
        poller=Mock()
        poller.poll.return_value=sample
        def connect():
            return psycopg.connect(DSN)
        self.assertTrue(ingest_one(poller,connect,IngestAuthorization(self.enroll_a,self.token_a,DeviceBinding(self.a,self.site_a,self.device_a)),self.now))
        self.assertFalse(ingest_one(poller,connect,IngestAuthorization(self.enroll_a,self.token_a,DeviceBinding(self.a,self.site_a,self.device_a)),self.now))
        poller.poll.assert_called_with(self.now)
    def test_worker_rejects_binding_mismatch(self):
        sample=NormalizedTelemetry(
            tenant_id=self.b,site_id=self.site_b,device_id=self.device_b,
            sampled_at=self.now,hostname='wrong',cpu_percent=10,
            memory_percent=20,uptime_seconds=10,disk_mounts=()
        )
        poller=Mock()
        poller.poll.return_value=sample
        with self.assertRaisesRegex(ValueError,"binding differs"):
            ingest_one(
                poller,lambda:psycopg.connect(DSN),
                IngestAuthorization(self.enroll_a,self.token_a,DeviceBinding(self.a,self.site_a,self.device_a)),
                self.now)
    def test_worker_invalid_credential_denied(self):
        with self.assertRaises(ValueError):
            IngestAuthorization(self.enroll_a,'short',DeviceBinding(self.a,self.site_a,self.device_a))
