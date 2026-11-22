"""Postgres 16 dispatch queue tests: at-least-once lease, retry and permissions."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
try:
    import psycopg
except ImportError:
    psycopg=None

DSN=os.getenv("SME_TEST_DATABASE_DSN")
ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(DSN and psycopg,"requires disposable PostgreSQL")
class DispatchQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db=psycopg.connect(DSN,autocommit=True)
        for p in sorted((ROOT/"migrations").glob("*.sql")):
            cls.db.execute(p.read_text())
    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def setUp(self):
        self.tenant,self.site,self.device,self.worker,self.other=[uuid4() for _ in range(5)]
        self.db.execute("INSERT INTO sme.tenants(id,slug,display_name) VALUES (%s,%s,'Dispatch')",
                        (self.tenant,"dispatch-"+self.tenant.hex[:12]))
        self.db.execute("INSERT INTO sme.sites(tenant_id,id,label) VALUES (%s,%s,'Site')",
                        (self.tenant,self.site))
        self.db.execute("INSERT INTO sme.assets(tenant_id,id,site_id,name) VALUES (%s,%s,%s,'Device')",
                        (self.tenant,self.device,self.site))
        self.id=self.db.execute(
            "INSERT INTO sme.asahi_alert_outbox(tenant_id,site_id,device_id,metric,transition,sampled_at,metric_value) "
            "VALUES (%s,%s,%s,'cpu','triggered',%s,95) RETURNING id",
            (self.tenant,self.site,self.device,datetime.now(timezone.utc))
        ).fetchone()[0]

    def claim(self,owner=None,lease=30,role="sme_dispatch"):
        with psycopg.connect(DSN) as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE "+role)
                return conn.execute(
                    "SELECT * FROM sme.claim_asahi_alert(%s,%s)",
                    (owner or self.worker,lease)
                ).fetchall()

    def finish(self,owner=None,success=True,retry=10,role="sme_dispatch"):
        with psycopg.connect(DSN) as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE "+role)
                return conn.execute(
                    "SELECT sme.finish_asahi_alert(%s,%s,%s,%s)",
                    (self.id,owner or self.worker,success,retry)
                ).fetchone()[0]

    def test_claim_and_ack_durable(self):
        rows=self.claim()
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0][:4],(self.id,self.tenant,self.site,self.device))
        self.assertFalse(self.claim(self.other))
        self.assertTrue(self.finish())
        self.assertEqual(self.claim(self.other),[])
        actual=self.db.execute(
            "SELECT delivered_at,delivery_attempts FROM sme.asahi_alert_outbox WHERE id=%s",
            (self.id,)
        ).fetchone()
        self.assertIsNotNone(actual[0])
        self.assertEqual(actual[1],1)

    def test_concurrent_claim_at_most_one(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            answers=list(pool.map(self.claim,(self.worker,self.other)))
        self.assertEqual(sorted(len(a) for a in answers),[0,1])

    def test_wrong_owner_denied(self):
        self.assertEqual(len(self.claim()),1)
        self.assertFalse(self.finish(self.other))
        self.assertTrue(self.finish(self.worker))

    def test_expired_lease_can_be_reclaimed(self):
        self.claim()
        self.db.execute(
            "UPDATE sme.asahi_alert_outbox SET delivery_lease_until=now()-interval '1 second' "
            "WHERE id=%s",(self.id,))
        self.assertEqual(len(self.claim(self.other)),1)
        self.assertFalse(self.finish(self.worker))
        self.assertTrue(self.finish(self.other))

    def test_failure_schedules_retry(self):
        self.claim()
        self.assertTrue(self.finish(success=False,retry=7))
        self.assertEqual(self.claim(self.other),[])
        row=self.db.execute(
            "SELECT delivery_attempts,delivered_at,dead_lettered_at,next_attempt_at>now() "
            "FROM sme.asahi_alert_outbox WHERE id=%s",(self.id,)).fetchone()
        self.assertEqual(row,(1,None,None,True))
        self.db.execute(
            "UPDATE sme.asahi_alert_outbox SET next_attempt_at=now()-interval '1 second' WHERE id=%s",
            (self.id,))
        self.assertEqual(len(self.claim(self.other)),1)

    def test_fifth_failure_dead_letters(self):
        for i in range(5):
            self.assertEqual(len(self.claim()),1)
            self.assertTrue(self.finish(success=False,retry=5))
            if i<4:
                self.db.execute(
                    "UPDATE sme.asahi_alert_outbox SET next_attempt_at=now()-interval '1 second' WHERE id=%s",
                    (self.id,))
        row=self.db.execute(
            "SELECT delivery_attempts,dead_lettered_at FROM sme.asahi_alert_outbox WHERE id=%s",
            (self.id,)).fetchone()
        self.assertEqual(row[0],5)
        self.assertIsNotNone(row[1])
        self.assertEqual(self.claim(self.other),[])

    def test_suspended_tenant_never_claimed(self):
        self.db.execute("UPDATE sme.tenants SET status='suspended' WHERE id=%s",
                        (self.tenant,))
        self.assertEqual(self.claim(),[])

    def test_invalid_lease_or_retry_rejected(self):
        self.assertEqual(self.claim(lease=4),[])
        self.assertEqual(self.claim(lease=301),[])
        self.assertEqual(len(self.claim()),1)
        self.assertFalse(self.finish(retry=4))
        self.assertFalse(self.finish(retry=3601))
        self.assertTrue(self.finish())

    def test_app_ingest_cannot_claim_or_finish(self):
        for role in ("sme_app","sme_ingest"):
            with self.subTest(role=role),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                self.claim(role=role)
            with self.subTest(role=role),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                self.finish(role=role)

    def test_dispatch_cannot_read_or_update_queue(self):
        for sql in (
            "SELECT * FROM sme.asahi_alert_outbox",
            "UPDATE sme.asahi_alert_outbox SET delivery_attempts=5",
        ):
            with self.subTest(sql=sql),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with self.db.transaction():
                    self.db.execute("SET LOCAL ROLE sme_dispatch")
                    self.db.execute(sql)

    def test_cannot_ack_twice(self):
        self.claim()
        self.assertTrue(self.finish())
        self.assertFalse(self.finish())
