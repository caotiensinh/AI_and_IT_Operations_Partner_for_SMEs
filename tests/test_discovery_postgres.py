"""Real database tests for discovery isolation and authenticated read API."""
import base64
import hashlib
import os
import secrets
import unittest
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timedelta, timezone

try:
    import psycopg
    from fastapi.testclient import TestClient
    from sme_partner.discovery_api import create_discovery_app
except ImportError:
    psycopg = None
    TestClient = None

DSN = os.getenv("SME_TEST_DATABASE_DSN")
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(DSN and psycopg and TestClient, "Requires disposable PostgreSQL and API client")
class DiscoveryPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = psycopg.connect(DSN, autocommit=True)
        for name in ("0001_tenant_foundation.sql", "0002_scoped_rbac.sql",
                     "0003_session_boundary.sql", "0008_discovery_read_model.sql"):
            cls.db.execute((ROOT / "migrations" / name).read_text())
        cls.a, cls.b, cls.sa, cls.sb, cls.ia, cls.ib, cls.ca, cls.cb = [uuid4() for _ in range(8)]
        cls.token = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
        cls.db.execute(
            "INSERT INTO sme.tenants(id,slug,display_name) VALUES "
            "(%s,%s,'Research A'),(%s,%s,'Research B')",
            (cls.a, "disca-"+cls.a.hex[:10], cls.b, "discb-"+cls.b.hex[:10]))
        cls.db.execute("INSERT INTO sme.sites(tenant_id,id,label) VALUES "
                       "(%s,%s,'A site'),(%s,%s,'B site')",
                       (cls.a,cls.sa,cls.b,cls.sb))
        cls.db.execute("INSERT INTO sme.identities(id,issuer,subject) VALUES "
                       "(%s,'https://id.example',%s),(%s,'https://id.example',%s)",
                       (cls.ia,cls.ia.hex,cls.ib,cls.ib.hex))
        cls.db.execute("INSERT INTO sme.memberships(tenant_id,identity_id) VALUES "
                       "(%s,%s),(%s,%s)",(cls.a,cls.ia,cls.b,cls.ib))
        cls.db.execute("INSERT INTO sme.role_assignments "
                       "(tenant_id,id,identity_id,role,scope_type) VALUES "
                       "(%s,%s,%s,'viewer','tenant')",
                       (cls.a,uuid4(),cls.ia))
        cls.db.execute(
            "INSERT INTO sme.sessions(id,identity_id,token_digest,expires_at) "
            "VALUES (%s,%s,%s,%s)", (uuid4(),cls.ia,
            hashlib.sha256(cls.token.encode()).digest(),
            datetime.now(timezone.utc)+timedelta(hours=1)))
        cls.db.execute("INSERT INTO sme.discovery_cases "
                       "(tenant_id,id,site_id,label,company_code) VALUES "
                       "(%s,%s,%s,'Beight assessment','B'),"
                       "(%s,%s,%s,'Ryoki assessment','R')",
                       (cls.a,cls.ca,cls.sa,cls.b,cls.cb,cls.sb))
        cls.source = uuid4()
        cls.db.execute("INSERT INTO sme.discovery_sources "
                       "(tenant_id,id,case_id,document_label,source_page) "
                       "VALUES (%s,%s,%s,'sample brief',1)",
                       (cls.a,cls.source,cls.ca))
        cls.req_id=uuid4()
        cls.db.execute("INSERT INTO sme.discovery_requirements "
                       "(tenant_id,id,case_id,source_id,statement,classification) "
                       "VALUES (%s,%s,%s,%s,'Customer information fragmentation','explicit')",
                       (cls.a,cls.req_id,cls.ca,cls.source))
        cls.client = TestClient(create_discovery_app(lambda: psycopg.connect(DSN)))

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.db.close()

    def request(self, tenant=None, token=None):
        return self.client.get(
            f"/v1/tenants/{tenant or self.a}/research-cases",
            headers={"Authorization":f"Bearer {token}"} if token else {},
        )

    def test_valid_session_sees_only_own_case(self):
        res = self.request(token=self.token)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual([x["label"] for x in res.json()["cases"]], ["Beight assessment"])

    def test_no_session_denied(self):
        self.assertEqual(self.request().status_code,401)

    def test_forged_session_denied(self):
        forged = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
        self.assertEqual(self.request(token=forged).status_code,403)

    def test_wrong_tenant_denied(self):
        self.assertEqual(self.request(self.b,self.token).status_code,403)

    def test_role_revocation_removes_visibility(self):
        self.db.execute("DELETE FROM sme.role_assignments "
                        "WHERE tenant_id=%s AND identity_id=%s",(self.a,self.ia))
        try:
            res = self.request(token=self.token)
            self.assertEqual(res.status_code,200,res.text)
            self.assertEqual(res.json()["cases"],[])
        finally:
            self.db.execute("INSERT INTO sme.role_assignments "
                            "(tenant_id,id,identity_id,role,scope_type) "
                            "VALUES (%s,%s,%s,'viewer','tenant')",
                            (self.a,uuid4(),self.ia))

    def test_rls_missing_context(self):
        with self.db.transaction():
            self.db.execute("SET LOCAL ROLE sme_app")
            self.assertEqual(self.db.execute("SELECT id FROM sme.discovery_cases").fetchall(),[])

    def test_rls_other_tenant_invisible(self):
        with self.db.transaction():
            self.db.execute("SET LOCAL ROLE sme_app")
            self.db.execute("SELECT set_config('sme.tenant_id',%s,true)",(str(self.a),))
            cases=self.db.execute("SELECT id FROM sme.discovery_cases ORDER BY id").fetchall()
            self.assertEqual(cases,[(self.ca,)])

    def test_runtime_cannot_write(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.db.transaction():
                self.db.execute("SET LOCAL ROLE sme_app")
                self.db.execute("SELECT set_config('sme.tenant_id',%s,true)",(str(self.a),))
                self.db.execute("DELETE FROM sme.discovery_cases WHERE tenant_id=%s",(self.a,))

    def test_cross_case_source_fk_rejected(self):
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            self.db.execute("INSERT INTO sme.discovery_requirements "
                            "(tenant_id,id,case_id,source_id,statement,classification) "
                            "VALUES (%s,%s,%s,%s,'invalid','explicit')",
                            (self.b,uuid4(),self.cb,self.source))

    def test_inferred_cannot_be_confirmed(self):
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.db.execute("INSERT INTO sme.discovery_requirements "
                            "(tenant_id,id,case_id,statement,classification,approval_state) "
                            "VALUES (%s,%s,%s,'hypothesis','inferred','confirmed')",
                            (self.a,uuid4(),self.ca))

    def test_explicit_requires_source(self):
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.db.execute("INSERT INTO sme.discovery_requirements "
                            "(tenant_id,id,case_id,statement,classification) "
                            "VALUES (%s,%s,%s,'no citation','explicit')",
                            (self.a,uuid4(),self.ca))

    def test_case_requirements_source_traceable(self):
        r=self.client.get(
            f"/v1/tenants/{self.a}/research-cases/{self.ca}/requirements",
            headers={"Authorization":f"Bearer {self.token}"})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()["requirements"],[{
            "id":str(self.req_id),
            "statement":"Customer information fragmentation",
            "classification":"explicit",
            "approval_state":"proposed",
            "source":{"document_label":"sample brief","page":1}
        }])

    def test_case_requirements_wrong_tenant_denied(self):
        r=self.client.get(
            f"/v1/tenants/{self.b}/research-cases/{self.cb}/requirements",
            headers={"Authorization":f"Bearer {self.token}"})
        self.assertEqual(r.status_code,403,r.text)

    def test_case_requirements_revoked_role_denied(self):
        self.db.execute("DELETE FROM sme.role_assignments "
                        "WHERE tenant_id=%s AND identity_id=%s",(self.a,self.ia))
        try:
            r=self.client.get(
                f"/v1/tenants/{self.a}/research-cases/{self.ca}/requirements",
                headers={"Authorization":f"Bearer {self.token}"})
            self.assertEqual(r.status_code,404,r.text)
        finally:
            self.db.execute("INSERT INTO sme.role_assignments "
                            "(tenant_id,id,identity_id,role,scope_type) "
                            "VALUES (%s,%s,%s,'viewer','tenant')",
                            (self.a,uuid4(),self.ia))
