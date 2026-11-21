"""Two-tenant Postgres E2E: latest Asahi telemetry is read-only and scoped."""
import base64
import hashlib
import os
import secrets
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

try:
    import psycopg
    from fastapi.testclient import TestClient
    from sme_partner.session_api import create_app
except ImportError:
    psycopg = None
    TestClient = None

ROOT = Path(__file__).resolve().parents[1]
DSN = os.getenv("SME_TEST_DATABASE_DSN")


def new_token():
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")


@unittest.skipUnless(DSN and psycopg and TestClient, "Requires disposable PostgreSQL")
class AsahiPostgresE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin = psycopg.connect(DSN, autocommit=True)
        for name in (
            "0001_tenant_foundation.sql", "0002_scoped_rbac.sql",
            "0003_session_boundary.sql", "0004_oidc_login_flow.sql", "0005_security_audit.sql",
            "0010_asahi_telemetry.sql", "0011_telemetry_audit.sql",
        ):
            cls.admin.execute((ROOT / "migrations" / name).read_text())
        (cls.a, cls.b, cls.user, cls.other, cls.site_a, cls.site_b,
         cls.asset_a, cls.asset_a2, cls.asset_b) = [uuid4() for _ in range(9)]
        cls.token, cls.other_token, cls.revoked_token = new_token(), new_token(), new_token()
        cls.now = datetime.now(timezone.utc).replace(microsecond=0)
        cls.admin.execute(
            "INSERT INTO sme.tenants(id,slug,display_name) "
            "VALUES (%s,%s,'Aichi'),(%s,%s,'Owari')",
            (cls.a,"asahi-"+cls.a.hex[:12],cls.b,"asahi-"+cls.b.hex[:12]))
        cls.admin.execute(
            "INSERT INTO sme.identities(id,issuer,subject) "
            "VALUES (%s,'https://id.example',%s),(%s,'https://id.example',%s)",
            (cls.user,cls.user.hex,cls.other,cls.other.hex))
        cls.admin.execute(
            "INSERT INTO sme.memberships(tenant_id,identity_id,status) "
            "VALUES (%s,%s,'active'),(%s,%s,'active')",
            (cls.a,cls.user,cls.b,cls.other))
        cls.admin.execute(
            "INSERT INTO sme.sites(tenant_id,id,label) "
            "VALUES (%s,%s,'Office'),(%s,%s,'Factory')",
            (cls.a,cls.site_a,cls.b,cls.site_b))
        cls.admin.execute(
            "INSERT INTO sme.assets(tenant_id,id,site_id,name) "
            "VALUES (%s,%s,%s,'Node A'),(%s,%s,%s,'Node A2'),(%s,%s,%s,'Node B')",
            (cls.a,cls.asset_a,cls.site_a,cls.a,cls.asset_a2,cls.site_a,
             cls.b,cls.asset_b,cls.site_b))
        cls.admin.execute(
            "INSERT INTO sme.role_assignments(tenant_id,id,identity_id,role,scope_type,site_id) "
            "VALUES (%s,%s,%s,'viewer','site',%s),"
            "(%s,%s,%s,'viewer','site',%s)",
            (cls.a,uuid4(),cls.user,cls.site_a,cls.b,uuid4(),cls.other,cls.site_b))
        for who,token,revoked in (
            (cls.user,cls.token,None),(cls.other,cls.other_token,None),
            (cls.user,cls.revoked_token,cls.now)):
            cls.admin.execute(
                "INSERT INTO sme.sessions(id,identity_id,token_digest,created_at,expires_at,revoked_at) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (uuid4(),who,hashlib.sha256(token.encode()).digest(),
                 cls.now-timedelta(hours=2),cls.now+timedelta(hours=1),revoked))
        for tenant,device,site,name,cpu,stamp in (
            (cls.a,cls.asset_a,cls.site_a,"aichi-node",25,cls.now-timedelta(minutes=1)),
            (cls.a,cls.asset_a,cls.site_a,"aichi-node",52,cls.now),
            (cls.a,cls.asset_a2,cls.site_a,"aichi-spare",None,cls.now),
            (cls.b,cls.asset_b,cls.site_b,"owari-node",87,cls.now)):
            cls.admin.execute(
                "INSERT INTO sme.asahi_samples(tenant_id,device_id,site_id,sampled_at,"
                "hostname,cpu_percent,memory_percent,uptime_seconds) "
                "VALUES (%s,%s,%s,%s,%s,%s,70,3600)",
                (tenant,device,site,stamp,name,cpu))
        cls.client = TestClient(create_app(lambda:psycopg.connect(DSN)))
    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.admin.close()
    def latest(self,tenant,token=None):
        return self.client.get(
            f"/v1/tenants/{tenant}/itops/asahi/latest",
            headers={"Authorization":f"Bearer {token}"} if token else {}
        )
    def test_authorized_telemetry_read_creates_audit(self):
        before = self.admin.execute(
            "SELECT count(*) FROM sme.security_audit "
            "WHERE tenant_id=%s AND action='telemetry.read'",(self.a,)
        ).fetchone()[0]
        response = self.latest(self.a,self.token)
        self.assertEqual(response.status_code,200,response.text)
        after = self.admin.execute(
            "SELECT count(*) FROM sme.security_audit "
            "WHERE tenant_id=%s AND action='telemetry.read'",(self.a,)
        ).fetchone()[0]
        self.assertEqual(after,before+1)

    def test_denied_cross_tenant_telemetry_leaves_no_audit(self):
        before = self.admin.execute(
            "SELECT count(*) FROM sme.security_audit "
            "WHERE tenant_id=%s AND action='telemetry.read'",(self.b,)
        ).fetchone()[0]
        self.assertEqual(self.latest(self.b,self.token).status_code,403)
        after = self.admin.execute(
            "SELECT count(*) FROM sme.security_audit "
            "WHERE tenant_id=%s AND action='telemetry.read'",(self.b,)
        ).fetchone()[0]
        self.assertEqual(after,before)

    def test_wrong_target_audit_pair_rejected(self):
        with self.admin.transaction():
            self.admin.execute("SET LOCAL ROLE sme_app")
            rejected = self.admin.execute(
                "SELECT sme.record_session_audit(%s,%s,'telemetry.read','asset',%s)",
                (hashlib.sha256(self.token.encode()).digest(),self.a,uuid4())
            ).fetchone()[0]
            self.assertFalse(rejected)

    def test_latest_sample_only(self):
        response=self.latest(self.a,self.token)
        self.assertEqual(response.status_code,200,response.text)
        values=response.json()["devices"]
        self.assertEqual(len(values),2)
        metrics={m["hostname"]:m["cpu_percent"] for m in values}
        self.assertEqual(metrics,{"aichi-node":52.0,"aichi-spare":None})
    def test_cross_tenant_denied(self):
        self.assertEqual(self.latest(self.b,self.token).status_code,403)
        self.assertEqual(self.latest(self.a,self.other_token).status_code,403)
    def test_tenant_b_only_sees_b(self):
        response=self.latest(self.b,self.other_token)
        self.assertEqual(response.status_code,200)
        self.assertEqual([x["hostname"] for x in response.json()["devices"]],["owari-node"])
    def test_no_session_or_revoked_denied(self):
        self.assertEqual(self.latest(self.a).status_code,401)
        self.assertEqual(self.latest(self.a,self.revoked_token).status_code,403)
    def test_role_revocation_hides_metrics(self):
        self.admin.execute("DELETE FROM sme.role_assignments WHERE tenant_id=%s AND identity_id=%s",
                           (self.a,self.user))
        try:
            r=self.latest(self.a,self.token)
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.json()["devices"],[])
        finally:
            self.admin.execute(
                "INSERT INTO sme.role_assignments(tenant_id,id,identity_id,role,scope_type,site_id) "
                "VALUES (%s,%s,%s,'viewer','site',%s)",
                (self.a,uuid4(),self.user,self.site_a))
    def test_runtime_cannot_write_metric(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.admin.transaction():
                self.admin.execute("SET LOCAL ROLE sme_app")
                self.admin.execute("SELECT set_config('sme.tenant_id',%s,true)",(str(self.a),))
                self.admin.execute(
                    "INSERT INTO sme.asahi_samples(tenant_id,device_id,site_id,sampled_at,hostname) "
                    "VALUES (%s,%s,%s,%s,'forged')",
                    (self.a,self.asset_a,self.site_a,self.now+timedelta(seconds=1)))
    def test_cross_tenant_raw_query_filtered(self):
        with self.admin.transaction():
            self.admin.execute("SET LOCAL ROLE sme_app")
            self.admin.execute("SELECT set_config('sme.tenant_id',%s,true)",(str(self.a),))
            rows=self.admin.execute(
                "SELECT DISTINCT tenant_id FROM sme.asahi_samples ORDER BY tenant_id").fetchall()
            self.assertEqual(rows,[(self.a,)])
    def test_invalid_site_relation_denied_by_fk(self):
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            self.admin.execute(
                "INSERT INTO sme.asahi_samples(tenant_id,device_id,site_id,sampled_at,hostname) "
                "VALUES (%s,%s,%s,%s,'wrong-site')",
                (self.a,self.asset_a,self.site_b,self.now+timedelta(minutes=1)))
    def test_site_scope_cannot_see_other_site(self):
        second_site = uuid4()
        other_asset = uuid4()
        self.admin.execute("INSERT INTO sme.sites(tenant_id,id,label) VALUES (%s,%s,'Extra')",
                           (self.a,second_site))
        self.admin.execute(
            "INSERT INTO sme.assets(tenant_id,id,site_id,name) VALUES (%s,%s,%s,'Hidden')",
            (self.a,other_asset,second_site))
        self.admin.execute(
            "INSERT INTO sme.asahi_samples(tenant_id,device_id,site_id,sampled_at,hostname,cpu_percent) "
            "VALUES (%s,%s,%s,%s,'hidden-node',12)",
            (self.a,other_asset,second_site,self.now))
        response=self.latest(self.a,self.token)
        self.assertEqual(response.status_code,200)
        self.assertNotIn("hidden-node",[r["hostname"] for r in response.json()["devices"]])
