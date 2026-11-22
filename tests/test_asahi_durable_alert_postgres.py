"""Real PostgreSQL 16 tests for credential-bound, durable Asahi alert outbox."""
import hashlib
import os
import secrets
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

try:
    import psycopg
except ImportError:
    psycopg=None

DSN=os.getenv("SME_TEST_DATABASE_DSN")
ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(DSN and psycopg,"requires disposable PostgreSQL 16")
class DurableAlertPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db=psycopg.connect(DSN,autocommit=True)
        for path in sorted((ROOT/"migrations").glob("*.sql")):
            cls.db.execute(path.read_text())
    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def setUp(self):
        self.tenant,self.other,self.site,self.other_site,self.device,self.other_device=[uuid4() for _ in range(6)]
        self.enrollment,self.other_enrollment=uuid4(),uuid4()
        self.token=secrets.token_urlsafe(32)
        self.other_token=secrets.token_urlsafe(32)
        self.now=datetime.now(timezone.utc).replace(microsecond=0)-timedelta(seconds=100)
        self.db.execute(
            "INSERT INTO sme.tenants(id,slug,display_name) VALUES (%s,%s,'A'),(%s,%s,'B')",
            (self.tenant,'alert-'+self.tenant.hex[:12],self.other,'alert-'+self.other.hex[:12]))
        self.db.execute(
            "INSERT INTO sme.sites(tenant_id,id,label) VALUES (%s,%s,'A'),(%s,%s,'B')",
            (self.tenant,self.site,self.other,self.other_site))
        self.db.execute(
            "INSERT INTO sme.assets(tenant_id,id,site_id,name) VALUES (%s,%s,%s,'A'),(%s,%s,%s,'B')",
            (self.tenant,self.device,self.site,self.other,self.other_device,self.other_site))
        for en,tenant,site,device,token in (
            (self.enrollment,self.tenant,self.site,self.device,self.token),
            (self.other_enrollment,self.other,self.other_site,self.other_device,self.other_token)):
            self.db.execute(
                "INSERT INTO sme.asahi_enrollments(id,tenant_id,site_id,device_id,credential_digest) "
                "VALUES (%s,%s,%s,%s,%s)",
                (en,tenant,site,device,hashlib.sha256(token.encode()).digest()))

    def put(self,step,cpu=95,memory=None,tenant=None,site=None,device=None):
        target=self.now+timedelta(seconds=step)
        self.db.execute(
            "INSERT INTO sme.asahi_samples(tenant_id,device_id,site_id,sampled_at,hostname,cpu_percent,memory_percent) "
            "VALUES (%s,%s,%s,%s,'test',%s,%s)",
            (tenant or self.tenant,device or self.device,site or self.site,target,cpu,memory))
        return target

    def evaluate(self,when,enrollment=None,token=None,connection=None,role="sme_ingest"):
        own=connection is None
        db=connection or psycopg.connect(DSN)
        try:
            with db.transaction():
                db.execute("SET LOCAL ROLE "+role)
                return db.execute(
                    "SELECT sme.evaluate_asahi_alert(%s,%s,%s)",
                    (enrollment or self.enrollment,
                     hashlib.sha256((token or self.token).encode()).digest(),when)
                ).fetchone()[0]
        finally:
            if own:
                db.close()

    def events(self,tenant=None):
        return self.db.execute(
            "SELECT metric,transition,sampled_at FROM sme.asahi_alert_outbox "
            "WHERE tenant_id=%s ORDER BY sampled_at,metric",
            (tenant or self.tenant,)
        ).fetchall()

    def test_trigger_only_after_two_samples_and_no_duplicate(self):
        first=self.put(1)
        second=self.put(2)
        third=self.put(3)
        self.assertEqual(self.evaluate(first),0)
        self.assertEqual(self.evaluate(second),1)
        self.assertEqual(self.evaluate(second),0)
        self.assertEqual(self.evaluate(third),0)
        self.assertEqual([(r[0],r[1]) for r in self.events()],[("cpu","triggered")])

    def test_restart_and_reverse_order_are_idempotent(self):
        a=self.put(1)
        b=self.put(2)
        self.evaluate(a)
        self.evaluate(b)
        self.assertEqual(self.evaluate(a),0)
        self.assertEqual(self.evaluate(b),0)
        self.assertEqual(len(self.events()),1)

    def test_hysteresis_clear_and_retrigger(self):
        for i,cpu in enumerate((95,95,85,80,95,95),start=1):
            stamp=self.put(i,cpu=cpu)
            self.evaluate(stamp)
        self.assertEqual(
            [(x[0],x[1]) for x in self.events()],
            [("cpu","triggered"),("cpu","cleared"),("cpu","triggered")])

    def test_cpu_memory_independent_null_ignored(self):
        one=self.put(1,cpu=None,memory=96)
        two=self.put(2,cpu=None,memory=99)
        self.assertEqual(self.evaluate(one),0)
        self.assertEqual(self.evaluate(two),1)
        self.assertEqual([(x[0],x[1]) for x in self.events()],[("memory","triggered")])

    def test_invalid_or_cross_tenant_credential_denied(self):
        t=self.put(1)
        self.assertEqual(self.evaluate(t,token=self.other_token),0)
        self.assertEqual(self.evaluate(t,enrollment=self.other_enrollment),0)
        self.assertEqual(self.events(),[])

    def test_revoked_enrollment_no_evaluation(self):
        t=self.put(1)
        self.db.execute("UPDATE sme.asahi_enrollments SET status='revoked' WHERE id=%s",
                        (self.enrollment,))
        self.assertEqual(self.evaluate(t),0)
        self.assertEqual(self.events(),[])

    def test_runtime_cannot_read_or_write_alert_tables(self):
        for query in ("SELECT * FROM sme.asahi_alert_state",
                      "INSERT INTO sme.asahi_alert_outbox(tenant_id,site_id,device_id,metric,transition,sampled_at,metric_value) "
                      "VALUES ('00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000001',"
                      "'00000000-0000-0000-0000-000000000001','cpu','triggered',now(),95)"):
            with self.subTest(query=query), self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with self.db.transaction():
                    self.db.execute("SET LOCAL ROLE sme_ingest")
                    self.db.execute(query)

    def test_web_role_cannot_call_evaluator(self):
        t=self.put(1)
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.evaluate(t,role="sme_app")

    def test_concurrent_same_sample_generates_one_event(self):
        first=self.put(1)
        second=self.put(2)
        self.evaluate(first)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(self.evaluate,(second,second)))
        self.assertEqual(sorted(results),[0,1])
        self.assertEqual(len(self.events()),1)

    def test_cross_tenant_independent_outbox(self):
        first=self.put(1)
        second=self.put(2)
        other_first=self.put(1,tenant=self.other,site=self.other_site,device=self.other_device)
        other_second=self.put(2,tenant=self.other,site=self.other_site,device=self.other_device)
        self.evaluate(first)
        self.evaluate(second)
        self.evaluate(other_first,enrollment=self.other_enrollment,token=self.other_token)
        self.evaluate(other_second,enrollment=self.other_enrollment,token=self.other_token)
        self.assertEqual(len(self.events()),1)
        self.assertEqual(len(self.events(tenant=self.other)),1)
