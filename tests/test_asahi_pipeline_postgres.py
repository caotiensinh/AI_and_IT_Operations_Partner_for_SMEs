"""CI E2E: Asahi JSON -> HTTPS adapter -> restricted worker -> PostgreSQL."""
import hashlib
import os
import secrets
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from uuid import uuid4

try:
    import httpx
    import psycopg
    from sme_partner.adapters.asahi import DeviceBinding
    from sme_partner.adapters.asahi_https import AsahiHTTPSPoller,TrustedAgentEndpoint,AgentPollRejected
    from sme_partner.asahi_ingest import ingest_one,IngestAuthorization
except ImportError:
    psycopg=None

DSN=os.getenv("SME_TEST_DATABASE_DSN")
ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(DSN and psycopg,"Needs disposable PostgreSQL and httpx")
class AsahiPollToDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin=psycopg.connect(DSN,autocommit=True)
        for file in sorted((ROOT/"migrations").glob("*.sql")):
            cls.admin.execute(file.read_text())
        cls.a,cls.b,cls.site_a,cls.site_b,cls.device_a,cls.device_b=[uuid4() for _ in range(6)]
        cls.enroll_a,cls.enroll_b=uuid4(),uuid4()
        cls.token_a,cls.token_b=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
        cls.time=datetime.now(timezone.utc).replace(microsecond=0)
        cls.admin.execute(
            "INSERT INTO sme.tenants(id,slug,display_name) VALUES (%s,%s,'Poll A'),(%s,%s,'Poll B')",
            (cls.a,'poll-'+cls.a.hex[:12],cls.b,'poll-'+cls.b.hex[:12]))
        cls.admin.execute("INSERT INTO sme.sites(tenant_id,id,label) VALUES (%s,%s,'A'),(%s,%s,'B')",
                          (cls.a,cls.site_a,cls.b,cls.site_b))
        cls.admin.execute(
            "INSERT INTO sme.assets(tenant_id,id,site_id,name) VALUES (%s,%s,%s,'A'),(%s,%s,%s,'B')",
            (cls.a,cls.device_a,cls.site_a,cls.b,cls.device_b,cls.site_b))
        for eid,tenant,site,dev,token in (
            (cls.enroll_a,cls.a,cls.site_a,cls.device_a,cls.token_a),
            (cls.enroll_b,cls.b,cls.site_b,cls.device_b,cls.token_b),
        ):
            cls.admin.execute(
                "INSERT INTO sme.asahi_enrollments(id,tenant_id,site_id,device_id,credential_digest) "
                "VALUES (%s,%s,%s,%s,%s)",
                (eid,tenant,site,dev,hashlib.sha256(token.encode()).digest()))
    @classmethod
    def tearDownClass(cls):
        cls.admin.close()
    def build(self,*,tenant,site,device,payload=None,status=200):
        binding=DeviceBinding(tenant,site,device)
        agent_token="e"*40
        endpoint=TrustedAgentEndpoint("https://agent.test.example/api/agent/status",agent_token,"/trusted/ca.pem",binding)
        if payload is None:
            payload={"hostname":"real-shape-agent","timestamp":int(self.time.timestamp()),
                     "cpu_pct":24.5,"memory_pct":42.0,"uptime_s":1500,"disks":[]}
        def respond(req):
            self.assertEqual(req.headers["Authorization"],"Bearer "+agent_token)
            self.assertEqual(req.url.path,"/api/agent/status")
            return httpx.Response(status,json=payload)
        client=httpx.Client(transport=httpx.MockTransport(respond))
        self.addCleanup(client.close)
        return AsahiHTTPSPoller(endpoint,client=client)
    def connect(self):
        return psycopg.connect(DSN)
    def test_full_pipeline_and_duplicate_replay(self):
        poller=self.build(tenant=self.a,site=self.site_a,device=self.device_a)
        auth=IngestAuthorization(self.enroll_a,self.token_a,DeviceBinding(self.a,self.site_a,self.device_a))
        self.assertTrue(ingest_one(poller,self.connect,auth,self.time))
        self.assertFalse(ingest_one(poller,self.connect,auth,self.time))
        row=self.admin.execute(
            "SELECT tenant_id,site_id,device_id,hostname,cpu_percent,memory_percent,uptime_seconds "
            "FROM sme.asahi_samples WHERE tenant_id=%s AND device_id=%s AND sampled_at=%s",
            (self.a,self.device_a,self.time)
        ).fetchone()
        self.assertEqual(row[0:4],(self.a,self.site_a,self.device_a,"real-shape-agent"))
        self.assertEqual(tuple(float(x) for x in row[4:6]),(24.5,42.0))
        self.assertEqual(row[6],1500)
    def test_high_cpu_polls_create_one_durable_alert(self):
        auth=IngestAuthorization(self.enroll_a,self.token_a,DeviceBinding(self.a,self.site_a,self.device_a))
        for step in (20,21):
            when=self.time+timedelta(seconds=step)
            payload={"hostname":"real-shape-agent","timestamp":int(when.timestamp()),
                     "cpu_pct":96,"memory_pct":42,"uptime_s":1500,"disks":[]}
            poller=self.build(tenant=self.a,site=self.site_a,device=self.device_a,payload=payload)
            self.assertTrue(ingest_one(poller,self.connect,auth,when))
            self.assertFalse(ingest_one(poller,self.connect,auth,when))
        records=self.admin.execute(
            "SELECT metric,transition FROM sme.asahi_alert_outbox "
            "WHERE tenant_id=%s AND device_id=%s ORDER BY sampled_at",
            (self.a,self.device_a)
        ).fetchall()
        self.assertEqual(records,[("cpu","triggered")])

    def test_failed_alert_evaluation_rolls_back_sample(self):
        when=self.time+timedelta(seconds=30)
        payload={"hostname":"atomic","timestamp":int(when.timestamp()),
                 "cpu_pct":99,"memory_pct":None,"uptime_s":200,"disks":[]}
        poller=self.build(tenant=self.a,site=self.site_a,device=self.device_a,payload=payload)
        auth=IngestAuthorization(self.enroll_a,self.token_a,DeviceBinding(self.a,self.site_a,self.device_a))
        function="sme.evaluate_asahi_alert(uuid,bytea,timestamptz)"
        self.admin.execute("REVOKE EXECUTE ON FUNCTION "+function+" FROM sme_ingest")
        try:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                ingest_one(poller,self.connect,auth,when)
            count=self.admin.execute(
                "SELECT count(*) FROM sme.asahi_samples WHERE tenant_id=%s AND device_id=%s AND sampled_at=%s",
                (self.a,self.device_a,when)
            ).fetchone()[0]
            self.assertEqual(count,0,"ingested sample must be rolled back when outbox evaluation fails")
        finally:
            self.admin.execute("GRANT EXECUTE ON FUNCTION "+function+" TO sme_ingest")

    def test_http_denied_does_not_persist(self):
        poller=self.build(tenant=self.b,site=self.site_b,device=self.device_b,status=401)
        auth=IngestAuthorization(self.enroll_b,self.token_b,DeviceBinding(self.b,self.site_b,self.device_b))
        with self.assertRaises(AgentPollRejected):
            ingest_one(poller,self.connect,auth,self.time)
        count=self.admin.execute(
            "SELECT count(*) FROM sme.asahi_samples WHERE tenant_id=%s AND device_id=%s",
            (self.b,self.device_b)).fetchone()[0]
        self.assertEqual(count,0)
    def test_wrong_enrollment_binding_does_not_persist(self):
        poller=self.build(tenant=self.a,site=self.site_a,device=self.device_a)
        auth=IngestAuthorization(self.enroll_b,self.token_b,DeviceBinding(self.b,self.site_b,self.device_b))
        with self.assertRaisesRegex(ValueError,"binding differs"):
            ingest_one(poller,self.connect,auth,self.time)
        count=self.admin.execute(
            "SELECT count(*) FROM sme.asahi_samples WHERE tenant_id=%s AND device_id=%s",
            (self.b,self.device_b)).fetchone()[0]
        self.assertEqual(count,0)
