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
                     "0003_session_boundary.sql", "0005_discovery_read_model.sql",
                     "0006_discovery_case_write.sql", "0007_discovery_idempotency.sql",
                     "0008_discovery_source_intake.sql",
                     "0009_discovery_requirement_intake.sql",
                     "0010_discovery_requirement_review.sql",
                     "0011_discovery_review_history_read.sql",
                     "0012_cookie_bff_tenants.sql"):
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

    def test_cases_keyset_pagination(self):
        extra = uuid4()
        self.db.execute(
            "INSERT INTO sme.discovery_cases(tenant_id,id,site_id,label,company_code) "
            "VALUES (%s,%s,%s,'Second case','OTHER')",(self.a,extra,self.sa))
        try:
            first = self.client.get(
                f"/v1/tenants/{self.a}/research-cases?limit=1",
                headers={"Authorization":f"Bearer {self.token}"})
            self.assertEqual(first.status_code,200,first.text)
            self.assertEqual(len(first.json()["cases"]),1)
            self.assertIsNotNone(first.json()["next_cursor"])
            second = self.client.get(
                f"/v1/tenants/{self.a}/research-cases",
                params={"limit":1,"after":first.json()["next_cursor"]},
                headers={"Authorization":f"Bearer {self.token}"})
            self.assertEqual(second.status_code,200,second.text)
            self.assertEqual(len(second.json()["cases"]),1)
            self.assertIsNone(second.json()["next_cursor"])
            self.assertEqual({first.json()["cases"][0]["id"],second.json()["cases"][0]["id"]},
                             {str(self.ca),str(extra)})
        finally:
            self.db.execute("DELETE FROM sme.discovery_cases WHERE tenant_id=%s AND id=%s",
                            (self.a,extra))

    def test_site_scope_filters_before_pagination(self):
        second_site,hidden_case,visible_case=uuid4(),uuid4(),uuid4()
        self.db.execute("INSERT INTO sme.sites(tenant_id,id,label) VALUES (%s,%s,'Second')",
                        (self.a,second_site))
        self.db.execute("INSERT INTO sme.discovery_cases "
                        "(tenant_id,id,site_id,label,company_code) VALUES "
                        "(%s,%s,%s,'Hidden','OTHER'),(%s,%s,%s,'Visible','OTHER')",
                        (self.a,hidden_case,second_site,self.a,visible_case,self.sa))
        self.db.execute("DELETE FROM sme.role_assignments WHERE tenant_id=%s AND identity_id=%s",
                        (self.a,self.ia))
        self.db.execute("INSERT INTO sme.role_assignments "
                        "(tenant_id,id,identity_id,role,scope_type,site_id) "
                        "VALUES (%s,%s,%s,'viewer','site',%s)",
                        (self.a,uuid4(),self.ia,self.sa))
        try:
            ids=[]
            after=None
            for _ in range(4):
                params={"limit":1}
                if after: params["after"]=after
                res=self.client.get(
                    f"/v1/tenants/{self.a}/research-cases",
                    params=params,headers={"Authorization":f"Bearer {self.token}"})
                self.assertEqual(res.status_code,200,res.text)
                ids.extend(x["id"] for x in res.json()["cases"])
                after=res.json()["next_cursor"]
                if after is None: break
            self.assertEqual(set(ids),{str(self.ca),str(visible_case)})
            self.assertNotIn(str(hidden_case),ids)
            denied=self.client.get(
                f"/v1/tenants/{self.a}/research-cases/{hidden_case}/requirements",
                headers={"Authorization":f"Bearer {self.token}"})
            self.assertEqual(denied.status_code,404,denied.text)
        finally:
            self.db.execute("DELETE FROM sme.role_assignments WHERE tenant_id=%s AND identity_id=%s",
                            (self.a,self.ia))
            self.db.execute("INSERT INTO sme.role_assignments "
                            "(tenant_id,id,identity_id,role,scope_type) "
                            "VALUES (%s,%s,%s,'viewer','tenant')",
                            (self.a,uuid4(),self.ia))
            self.db.execute("DELETE FROM sme.discovery_cases WHERE tenant_id=%s AND id IN (%s,%s)",
                            (self.a,hidden_case,visible_case))
            self.db.execute("DELETE FROM sme.sites WHERE tenant_id=%s AND id=%s",
                            (self.a,second_site))

    def test_requirement_pagination_and_traceability(self):
        extra=uuid4()
        self.db.execute("INSERT INTO sme.discovery_requirements "
                        "(tenant_id,id,case_id,statement,classification) "
                        "VALUES (%s,%s,%s,'Unconfirmed hypothesis','inferred')",
                        (self.a,extra,self.ca))
        try:
            endpoint=f"/v1/tenants/{self.a}/research-cases/{self.ca}/requirements"
            first=self.client.get(endpoint,params={"limit":1},
                                  headers={"Authorization":f"Bearer {self.token}"})
            self.assertEqual(first.status_code,200,first.text)
            self.assertEqual(len(first.json()["requirements"]),1)
            self.assertIsNotNone(first.json()["next_cursor"])
            second=self.client.get(endpoint,params={"limit":1,"after":first.json()["next_cursor"]},
                                   headers={"Authorization":f"Bearer {self.token}"})
            self.assertEqual(second.status_code,200,second.text)
            self.assertEqual(len(second.json()["requirements"]),1)
            self.assertIsNone(second.json()["next_cursor"])
            both=first.json()["requirements"]+second.json()["requirements"]
            self.assertEqual({r["classification"] for r in both},{"explicit","inferred"})
            inferred=next(r for r in both if r["classification"]=="inferred")
            self.assertIsNone(inferred["source"])
        finally:
            self.db.execute("DELETE FROM sme.discovery_requirements WHERE tenant_id=%s AND id=%s",
                            (self.a,extra))

    def test_invalid_limit_and_cursor_rejected(self):
        endpoint=f"/v1/tenants/{self.a}/research-cases"
        for params in ({"limit":0},{"limit":101},{"limit":1,"after":"not-a-uuid"}):
            with self.subTest(params=params):
                r=self.client.get(endpoint,params=params,
                                  headers={"Authorization":f"Bearer {self.token}"})
                self.assertEqual(r.status_code,422,r.text)

    def post_case(self, tenant=None, site=None, token=None, label="Process assessment", key=None):
        headers={"Idempotency-Key": key or secrets.token_urlsafe(24)}
        if token: headers["Authorization"]=f"Bearer {token}"
        return self.client.post(
            f"/v1/tenants/{tenant or self.a}/research-cases",
            json={"site_id":str(site or self.sa),"label":label,"company_code":"OTHER"},
            headers=headers,
        )

    def test_case_create_manager_site_permission_and_atomic_audit(self):
        self.db.execute("DELETE FROM sme.role_assignments WHERE tenant_id=%s AND identity_id=%s",
                        (self.a,self.ia))
        self.db.execute(
            "INSERT INTO sme.role_assignments "
            "(tenant_id,id,identity_id,role,scope_type,site_id) "
            "VALUES (%s,%s,%s,'manager','site',%s)",
            (self.a,uuid4(),self.ia,self.sa))
        created=None
        try:
            result=self.post_case(token=self.token)
            self.assertEqual(result.status_code,201,result.text)
            created=result.json()["case_id"]
            record=self.db.execute(
                "SELECT site_id,label,status FROM sme.discovery_cases WHERE tenant_id=%s AND id=%s",
                (self.a,created)).fetchone()
            self.assertEqual(record,(self.sa,"Process assessment","research"))
            audit=self.db.execute(
                "SELECT actor_identity_id,action FROM sme.discovery_change_events "
                "WHERE tenant_id=%s AND case_id=%s",(self.a,created)).fetchall()
            self.assertEqual(audit,[(self.ia,"case.created")])
        finally:
            if created:
                self.db.execute("DELETE FROM sme.discovery_create_requests "
                                "WHERE tenant_id=%s AND case_id=%s",(self.a,created))
                self.db.execute("DELETE FROM sme.discovery_change_events "
                                "WHERE tenant_id=%s AND case_id=%s",(self.a,created))
                self.db.execute("DELETE FROM sme.discovery_cases WHERE tenant_id=%s AND id=%s",
                                (self.a,created))
            self.db.execute("DELETE FROM sme.role_assignments "
                            "WHERE tenant_id=%s AND identity_id=%s",(self.a,self.ia))
            self.db.execute("INSERT INTO sme.role_assignments "
                            "(tenant_id,id,identity_id,role,scope_type) "
                            "VALUES (%s,%s,%s,'viewer','tenant')",(self.a,uuid4(),self.ia))

    def test_case_create_viewer_denied_with_no_audit(self):
        before=self.db.execute("SELECT count(*) FROM sme.discovery_change_events "
                               "WHERE tenant_id=%s",(self.a,)).fetchone()[0]
        self.assertEqual(self.post_case(token=self.token).status_code,403)
        after=self.db.execute("SELECT count(*) FROM sme.discovery_change_events "
                              "WHERE tenant_id=%s",(self.a,)).fetchone()[0]
        self.assertEqual(before,after)

    def test_case_create_missing_forged_and_wrong_tenant_denied(self):
        forged=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
        self.assertEqual(self.post_case().status_code,401)
        self.assertEqual(self.post_case(token=forged).status_code,403)
        self.assertEqual(self.post_case(tenant=self.b,site=self.sb,token=self.token).status_code,403)

    def test_case_create_invalid_site_denied_even_if_manager(self):
        self.db.execute("DELETE FROM sme.role_assignments "
                        "WHERE tenant_id=%s AND identity_id=%s",(self.a,self.ia))
        self.db.execute("INSERT INTO sme.role_assignments "
                        "(tenant_id,id,identity_id,role,scope_type) "
                        "VALUES (%s,%s,%s,'manager','tenant')",(self.a,uuid4(),self.ia))
        try:
            self.assertEqual(self.post_case(site=self.sb,token=self.token).status_code,403)
            self.assertEqual(self.post_case(site=uuid4(),token=self.token).status_code,403)
        finally:
            self.db.execute("DELETE FROM sme.role_assignments "
                            "WHERE tenant_id=%s AND identity_id=%s",(self.a,self.ia))
            self.db.execute("INSERT INTO sme.role_assignments "
                            "(tenant_id,id,identity_id,role,scope_type) "
                            "VALUES (%s,%s,%s,'viewer','tenant')",(self.a,uuid4(),self.ia))

    def test_case_create_invalid_payload_rejected(self):
        for label in ("", "   ", "X"*201):
            with self.subTest(label=label[:10]):
                self.assertEqual(self.post_case(token=self.token,label=label).status_code,422)
        resp=self.client.post(
            f"/v1/tenants/{self.a}/research-cases",
            json={"site_id":str(self.sa),"label":"case","company_code":"UNKNOWN"},
            headers={"Authorization":f"Bearer {self.token}"})
        self.assertEqual(resp.status_code,422)

    def test_direct_app_cannot_write_or_read_audit(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.db.transaction():
                self.db.execute("SET LOCAL ROLE sme_app")
                self.db.execute("SELECT * FROM sme.discovery_change_events")
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.db.transaction():
                self.db.execute("SET LOCAL ROLE sme_app")
                self.db.execute("INSERT INTO sme.discovery_cases "
                                "(tenant_id,id,site_id,label,company_code) "
                                "VALUES (%s,%s,%s,'Bypass','OTHER')",(self.a,uuid4(),self.sa))

    def test_replay_is_single_case_single_audit(self):
        self.db.execute("DELETE FROM sme.role_assignments WHERE tenant_id=%s AND identity_id=%s",
                        (self.a,self.ia))
        self.db.execute("INSERT INTO sme.role_assignments "
                        "(tenant_id,id,identity_id,role,scope_type,site_id) "
                        "VALUES (%s,%s,%s,'manager','site',%s)",
                        (self.a,uuid4(),self.ia,self.sa))
        key=secrets.token_urlsafe(24)
        created=None
        try:
            a=self.post_case(token=self.token,key=key)
            b=self.post_case(token=self.token,key=key)
            self.assertEqual((a.status_code,b.status_code),(201,200),(a.text,b.text))
            self.assertFalse(a.json()["replayed"])
            self.assertTrue(b.json()["replayed"])
            created=a.json()["case_id"]
            self.assertEqual(created,b.json()["case_id"])
            counts=self.db.execute(
                "SELECT (SELECT count(*) FROM sme.discovery_cases WHERE tenant_id=%s AND id=%s),"
                "(SELECT count(*) FROM sme.discovery_change_events WHERE tenant_id=%s AND case_id=%s)",
                (self.a,created,self.a,created)).fetchone()
            self.assertEqual(counts,(1,1))
            conflict=self.post_case(token=self.token,key=key,label="Different payload")
            self.assertEqual(conflict.status_code,409,conflict.text)
        finally:
            if created:
                self.db.execute("DELETE FROM sme.discovery_create_requests WHERE tenant_id=%s AND case_id=%s",
                                (self.a,created))
                self.db.execute("DELETE FROM sme.discovery_change_events WHERE tenant_id=%s AND case_id=%s",
                                (self.a,created))
                self.db.execute("DELETE FROM sme.discovery_cases WHERE tenant_id=%s AND id=%s",
                                (self.a,created))
            self.db.execute("DELETE FROM sme.role_assignments WHERE tenant_id=%s AND identity_id=%s",
                            (self.a,self.ia))
            self.db.execute("INSERT INTO sme.role_assignments "
                            "(tenant_id,id,identity_id,role,scope_type) VALUES (%s,%s,%s,'viewer','tenant')",
                            (self.a,uuid4(),self.ia))

    def test_idempotency_key_validation(self):
        for key in (None,"short","X"*129,"x"*20+"!","not space allowed"):
            with self.subTest(key=key):
                result=self.client.post(
                    f"/v1/tenants/{self.a}/research-cases",
                    json={"site_id":str(self.sa),"label":"Case","company_code":"OTHER"},
                    headers={"Authorization":f"Bearer {self.token}",
                             **({"Idempotency-Key":key} if key else {})})
                self.assertEqual(result.status_code,422,result.text)

    def test_legacy_non_idempotent_function_execute_revoked(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.db.transaction():
                self.db.execute("SET LOCAL ROLE sme_app")
                self.db.execute("SELECT sme.create_discovery_case(%s,%s,%s,%s,%s)",
                                (hashlib.sha256(self.token.encode()).digest(),
                                 self.a,self.sa,"Unsafe duplicate","OTHER"))

    def test_concurrent_replay_same_key(self):
        from concurrent.futures import ThreadPoolExecutor
        self.db.execute("DELETE FROM sme.role_assignments WHERE tenant_id=%s AND identity_id=%s",
                        (self.a,self.ia))
        self.db.execute("INSERT INTO sme.role_assignments "
                        "(tenant_id,id,identity_id,role,scope_type) "
                        "VALUES (%s,%s,%s,'manager','tenant')",
                        (self.a,uuid4(),self.ia))
        key=secrets.token_urlsafe(24)
        created=None
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                pending=[pool.submit(self.post_case,token=self.token,key=key) for _ in range(2)]
                results=[p.result(timeout=20) for p in pending]
            self.assertEqual(sorted(r.status_code for r in results),[200,201],
                             [r.text for r in results])
            created=results[0].json()["case_id"]
            self.assertEqual(created,results[1].json()["case_id"])
            events=self.db.execute(
                "SELECT count(*) FROM sme.discovery_change_events "
                "WHERE tenant_id=%s AND case_id=%s",(self.a,created)).fetchone()[0]
            self.assertEqual(events,1)
        finally:
            if created:
                self.db.execute("DELETE FROM sme.discovery_create_requests WHERE tenant_id=%s AND case_id=%s",
                                (self.a,created))
                self.db.execute("DELETE FROM sme.discovery_change_events WHERE tenant_id=%s AND case_id=%s",
                                (self.a,created))
                self.db.execute("DELETE FROM sme.discovery_cases WHERE tenant_id=%s AND id=%s",
                                (self.a,created))
            self.db.execute("DELETE FROM sme.role_assignments WHERE tenant_id=%s AND identity_id=%s",
                            (self.a,self.ia))
            self.db.execute("INSERT INTO sme.role_assignments "
                            "(tenant_id,id,identity_id,role,scope_type) "
                            "VALUES (%s,%s,%s,'viewer','tenant')",(self.a,uuid4(),self.ia))

    def test_source_metadata_create_replay_conflict_and_audit(self):
        self.db.execute("DELETE FROM sme.role_assignments WHERE tenant_id=%s AND identity_id=%s",
                        (self.a,self.ia))
        self.db.execute("INSERT INTO sme.role_assignments "
                        "(tenant_id,id,identity_id,role,scope_type,site_id) "
                        "VALUES (%s,%s,%s,'manager','site',%s)",
                        (self.a,uuid4(),self.ia,self.sa))
        new_source=uuid4()
        endpoint=f"/v1/tenants/{self.a}/research-cases/{self.ca}/sources"
        headers={"Authorization":f"Bearer {self.token}"}
        data={"source_id":str(new_source),"document_label":"  Synthetic source  ","page":1}
        try:
            first=self.client.post(endpoint,json=data,headers=headers)
            replay=self.client.post(endpoint,json=data,headers=headers)
            self.assertEqual((first.status_code,replay.status_code),(201,200),
                             (first.text,replay.text))
            self.assertEqual(first.json()["source_id"],str(new_source))
            self.assertFalse(first.json()["replayed"])
            self.assertTrue(replay.json()["replayed"])
            record=self.db.execute(
                "SELECT document_label,source_page FROM sme.discovery_sources "
                "WHERE tenant_id=%s AND id=%s",(self.a,new_source)).fetchone()
            self.assertEqual(record,("Synthetic source",1))
            audit=self.db.execute(
                "SELECT actor_identity_id,action,subject_id "
                "FROM sme.discovery_change_events WHERE tenant_id=%s AND subject_id=%s",
                (self.a,new_source)).fetchall()
            self.assertEqual(audit,[(self.ia,"source.created",new_source)])
            conflict=self.client.post(endpoint,headers=headers,json={
                **data,"page":2})
            self.assertEqual(conflict.status_code,409,conflict.text)
            self.assertEqual(self.db.execute(
                "SELECT count(*) FROM sme.discovery_change_events "
                "WHERE tenant_id=%s AND subject_id=%s",(self.a,new_source)).fetchone()[0],1)
        finally:
            self.db.execute("DELETE FROM sme.discovery_change_events "
                            "WHERE tenant_id=%s AND subject_id=%s",(self.a,new_source))
            self.db.execute("DELETE FROM sme.discovery_sources "
                            "WHERE tenant_id=%s AND id=%s",(self.a,new_source))
            self.db.execute("DELETE FROM sme.role_assignments "
                            "WHERE tenant_id=%s AND identity_id=%s",(self.a,self.ia))
            self.db.execute("INSERT INTO sme.role_assignments "
                            "(tenant_id,id,identity_id,role,scope_type) "
                            "VALUES (%s,%s,%s,'viewer','tenant')",(self.a,uuid4(),self.ia))

    def test_source_metadata_denied_viewer_and_foreign_case(self):
        endpoint=f"/v1/tenants/{self.a}/research-cases/{self.ca}/sources"
        payload={"source_id":str(uuid4()),"document_label":"Synthetic","page":1}
        self.assertEqual(self.client.post(endpoint,json=payload,
            headers={"Authorization":f"Bearer {self.token}"}).status_code,403)
        self.assertEqual(self.client.post(endpoint,json=payload).status_code,401)
        cross=f"/v1/tenants/{self.b}/research-cases/{self.cb}/sources"
        self.assertEqual(self.client.post(cross,json=payload,
            headers={"Authorization":f"Bearer {self.token}"}).status_code,403)
        self.assertEqual(self.client.post(endpoint,json={**payload,"page":0},
            headers={"Authorization":f"Bearer {self.token}"}).status_code,422)

    def test_app_runtime_cannot_insert_source_or_read_audit(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.db.transaction():
                self.db.execute("SET LOCAL ROLE sme_app")
                self.db.execute("INSERT INTO sme.discovery_sources "
                                "(tenant_id,id,case_id,document_label,source_page) "
                                "VALUES (%s,%s,%s,'Bypass',1)",
                                (self.a,uuid4(),self.ca))

    def test_requirement_intake_explicit_replay_conflict_and_audit(self):
        self.db.execute("DELETE FROM sme.role_assignments WHERE tenant_id=%s AND identity_id=%s",
                        (self.a,self.ia))
        self.db.execute("INSERT INTO sme.role_assignments "
                        "(tenant_id,id,identity_id,role,scope_type,site_id) "
                        "VALUES (%s,%s,%s,'manager','site',%s)",
                        (self.a,uuid4(),self.ia,self.sa))
        req=uuid4()
        endpoint=f"/v1/tenants/{self.a}/research-cases/{self.ca}/requirements"
        payload={"requirement_id":str(req),"statement":"  Need safer reporting  ",
                 "classification":"explicit","source_id":str(self.source)}
        headers={"Authorization":f"Bearer {self.token}"}
        try:
            first=self.client.post(endpoint,json=payload,headers=headers)
            replay=self.client.post(endpoint,json=payload,headers=headers)
            self.assertEqual((first.status_code,replay.status_code),(201,200),
                             (first.text,replay.text))
            self.assertEqual(first.json()["approval_state"],"proposed")
            self.assertTrue(replay.json()["replayed"])
            row=self.db.execute(
                "SELECT statement,classification,approval_state,source_id "
                "FROM sme.discovery_requirements WHERE tenant_id=%s AND id=%s",
                (self.a,req)).fetchone()
            self.assertEqual(row,("Need safer reporting","explicit","proposed",self.source))
            audit=self.db.execute("SELECT actor_identity_id,action,subject_id "
                                  "FROM sme.discovery_change_events "
                                  "WHERE tenant_id=%s AND subject_id=%s",
                                  (self.a,req)).fetchall()
            self.assertEqual(audit,[(self.ia,"requirement.created",req)])
            changed=self.client.post(endpoint,json={**payload,"statement":"Changed"},
                                     headers=headers)
            self.assertEqual(changed.status_code,409,changed.text)
        finally:
            self.db.execute("DELETE FROM sme.discovery_change_events "
                            "WHERE tenant_id=%s AND subject_id=%s",(self.a,req))
            self.db.execute("DELETE FROM sme.discovery_requirements "
                            "WHERE tenant_id=%s AND id=%s",(self.a,req))
            self.db.execute("DELETE FROM sme.role_assignments "
                            "WHERE tenant_id=%s AND identity_id=%s",(self.a,self.ia))
            self.db.execute("INSERT INTO sme.role_assignments "
                            "(tenant_id,id,identity_id,role,scope_type) "
                            "VALUES (%s,%s,%s,'viewer','tenant')",(self.a,uuid4(),self.ia))

    def test_requirement_intake_rejects_bad_evidence_and_cross_case(self):
        endpoint=f"/v1/tenants/{self.a}/research-cases/{self.ca}/requirements"
        headers={"Authorization":f"Bearer {self.token}"}
        base={"requirement_id":str(uuid4()),"statement":"Hypothesis",
              "classification":"explicit"}
        self.assertEqual(self.client.post(endpoint,json=base,headers=headers).status_code,422)
        self.assertEqual(self.client.post(endpoint,json={
            **base,"source_id":str(uuid4())},headers=headers).status_code,403)
        self.assertEqual(self.client.post(endpoint,json={
            **base,"classification":"CERTAIN","source_id":str(self.source)},
            headers=headers).status_code,422)
        self.assertEqual(self.client.post(endpoint,json={
            **base,"classification":"inferred"},headers=headers).status_code,403)
        self.assertEqual(self.client.post(endpoint,json={
            **base,"source_id":str(self.source)},headers={}).status_code,401)

    def test_requirement_intake_inferred_proposed_without_source(self):
        self.db.execute("DELETE FROM sme.role_assignments WHERE tenant_id=%s AND identity_id=%s",
                        (self.a,self.ia))
        self.db.execute("INSERT INTO sme.role_assignments "
                        "(tenant_id,id,identity_id,role,scope_type) "
                        "VALUES (%s,%s,%s,'manager','tenant')",(self.a,uuid4(),self.ia))
        req=uuid4()
        endpoint=f"/v1/tenants/{self.a}/research-cases/{self.ca}/requirements"
        try:
            result=self.client.post(endpoint,json={
                "requirement_id":str(req),"statement":"Potential optimization",
                "classification":"inferred"},
                headers={"Authorization":f"Bearer {self.token}"})
            self.assertEqual(result.status_code,201,result.text)
            self.assertEqual(self.db.execute(
                "SELECT approval_state FROM sme.discovery_requirements "
                "WHERE tenant_id=%s AND id=%s",(self.a,req)).fetchone()[0],"proposed")
        finally:
            self.db.execute("DELETE FROM sme.discovery_change_events WHERE tenant_id=%s AND subject_id=%s",
                            (self.a,req))
            self.db.execute("DELETE FROM sme.discovery_requirements WHERE tenant_id=%s AND id=%s",
                            (self.a,req))
            self.db.execute("DELETE FROM sme.role_assignments WHERE tenant_id=%s AND identity_id=%s",
                            (self.a,self.ia))
            self.db.execute("INSERT INTO sme.role_assignments "
                            "(tenant_id,id,identity_id,role,scope_type) "
                            "VALUES (%s,%s,%s,'viewer','tenant')",(self.a,uuid4(),self.ia))

    def test_runtime_cannot_write_requirements_directly(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.db.transaction():
                self.db.execute("SET LOCAL ROLE sme_app")
                self.db.execute("INSERT INTO sme.discovery_requirements "
                                "(tenant_id,id,case_id,statement,classification) "
                                "VALUES (%s,%s,%s,'Bypass','inferred')",
                                (self.a,uuid4(),self.ca))

    def _review(self, req_id, decision, version=0, token=None, reason="Reviewed supporting evidence"):
        return self.client.post(
            f"/v1/tenants/{self.a}/research-cases/{self.ca}/requirements/{req_id}/review",
            json={"expected_version":version,"decision":decision,"rationale":reason},
            headers={"Authorization":f"Bearer {token or self.token}"},
        )

    def _with_manager(self):
        self.db.execute("DELETE FROM sme.role_assignments WHERE tenant_id=%s AND identity_id=%s",
                        (self.a,self.ia))
        self.db.execute("INSERT INTO sme.role_assignments "
                        "(tenant_id,id,identity_id,role,scope_type,site_id) "
                        "VALUES (%s,%s,%s,'manager','site',%s)",
                        (self.a,uuid4(),self.ia,self.sa))

    def _restore_viewer(self):
        self.db.execute("DELETE FROM sme.role_assignments WHERE tenant_id=%s AND identity_id=%s",
                        (self.a,self.ia))
        self.db.execute("INSERT INTO sme.role_assignments "
                        "(tenant_id,id,identity_id,role,scope_type) "
                        "VALUES (%s,%s,%s,'viewer','tenant')",(self.a,uuid4(),self.ia))

    def test_explicit_review_confirm_is_versioned_and_audited(self):
        self._with_manager()
        try:
            first=self._review(self.req_id,"confirmed")
            self.assertEqual(first.status_code,200,first.text)
            self.assertEqual(first.json()["approval_state"],"confirmed")
            self.assertEqual(first.json()["review_version"],1)
            self.assertTrue(first.json()["updated"])
            self.assertEqual(self.db.execute(
                "SELECT approval_state,review_version FROM sme.discovery_requirements "
                "WHERE tenant_id=%s AND id=%s",(self.a,self.req_id)).fetchone(),
                ("confirmed",1))
            history=self.db.execute(
                "SELECT actor_identity_id,previous_state,next_state,review_version,rationale "
                "FROM sme.discovery_requirement_reviews "
                "WHERE tenant_id=%s AND requirement_id=%s",
                (self.a,self.req_id)).fetchall()
            self.assertEqual(history,[(self.ia,"proposed","confirmed",1,"Reviewed supporting evidence")])
            count=self.db.execute(
                "SELECT count(*) FROM sme.discovery_change_events "
                "WHERE tenant_id=%s AND subject_id=%s AND action='requirement.reviewed'",
                (self.a,self.req_id)).fetchone()[0]
            self.assertEqual(count,1)
            repeat=self._review(self.req_id,"confirmed",version=1)
            self.assertEqual(repeat.status_code,200,repeat.text)
            self.assertFalse(repeat.json()["updated"])
            self.assertEqual(self._review(self.req_id,"confirmed",version=0).status_code,409)
            self.assertEqual(self._review(self.req_id,"rejected",version=1).status_code,422)
            self.assertEqual(self.db.execute(
                "SELECT count(*) FROM sme.discovery_requirement_reviews "
                "WHERE tenant_id=%s AND requirement_id=%s",(self.a,self.req_id)).fetchone()[0],1)
        finally:
            self.db.execute("DELETE FROM sme.discovery_change_events "
                            "WHERE tenant_id=%s AND subject_id=%s AND action='requirement.reviewed'",
                            (self.a,self.req_id))
            self.db.execute("DELETE FROM sme.discovery_requirement_reviews "
                            "WHERE tenant_id=%s AND requirement_id=%s",(self.a,self.req_id))
            self.db.execute("UPDATE sme.discovery_requirements "
                            "SET approval_state='proposed',review_version=0 "
                            "WHERE tenant_id=%s AND id=%s",(self.a,self.req_id))
            self._restore_viewer()

    def test_inferred_cannot_be_confirmed_but_can_be_rejected(self):
        inferred=uuid4()
        self.db.execute("INSERT INTO sme.discovery_requirements "
                        "(tenant_id,id,case_id,statement,classification) "
                        "VALUES (%s,%s,%s,'Potential savings','inferred')",
                        (self.a,inferred,self.ca))
        self._with_manager()
        try:
            self.assertEqual(self._review(inferred,"confirmed").status_code,422)
            response=self._review(inferred,"rejected")
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual((response.json()["approval_state"],response.json()["review_version"]),
                             ("rejected",1))
            self.assertEqual(self.db.execute(
                "SELECT approval_state FROM sme.discovery_requirements "
                "WHERE tenant_id=%s AND id=%s",(self.a,inferred)).fetchone()[0],"rejected")
            self.assertEqual(self._review(inferred,"confirmed",version=1).status_code,422)
        finally:
            self.db.execute("DELETE FROM sme.discovery_change_events "
                            "WHERE tenant_id=%s AND subject_id=%s",(self.a,inferred))
            self.db.execute("DELETE FROM sme.discovery_requirement_reviews "
                            "WHERE tenant_id=%s AND requirement_id=%s",(self.a,inferred))
            self.db.execute("DELETE FROM sme.discovery_requirements "
                            "WHERE tenant_id=%s AND id=%s",(self.a,inferred))
            self._restore_viewer()

    def test_viewer_cannot_review_and_no_history_written(self):
        response=self._review(self.req_id,"confirmed")
        self.assertEqual(response.status_code,403,response.text)
        self.assertEqual(self.db.execute(
            "SELECT count(*) FROM sme.discovery_requirement_reviews "
            "WHERE tenant_id=%s AND requirement_id=%s",
            (self.a,self.req_id)).fetchone()[0],0)

    def test_review_foreign_tenant_and_invalid_payload_denied(self):
        self._with_manager()
        try:
            wrong=self.client.post(
                f"/v1/tenants/{self.b}/research-cases/{self.cb}/requirements/{self.req_id}/review",
                json={"expected_version":0,"decision":"confirmed",
                      "rationale":"Unauthorized cross tenant"},
                headers={"Authorization":f"Bearer {self.token}"})
            self.assertEqual(wrong.status_code,403,wrong.text)
            self.assertEqual(self._review(uuid4(),"confirmed").status_code,403)
            self.assertEqual(self._review(self.req_id,"confirmed",reason="short").status_code,422)
            self.assertEqual(self._review(self.req_id,"confirmed",version=-1).status_code,422)
            self.assertEqual(self._review(self.req_id,"invalid").status_code,422)
        finally:
            self._restore_viewer()

    def test_app_cannot_directly_update_or_read_review_history(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.db.transaction():
                self.db.execute("SET LOCAL ROLE sme_app")
                self.db.execute("UPDATE sme.discovery_requirements "
                                "SET approval_state='confirmed' WHERE tenant_id=%s AND id=%s",
                                (self.a,self.req_id))
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.db.transaction():
                self.db.execute("SET LOCAL ROLE sme_app")
                self.db.execute("SELECT * FROM sme.discovery_requirement_reviews")

    def test_review_history_manager_reads_reviewer_and_reason(self):
        self._with_manager()
        url=f"/v1/tenants/{self.a}/research-cases/{self.ca}/requirements/{self.req_id}/reviews"
        try:
            before=self.client.get(url,headers={"Authorization":f"Bearer {self.token}"})
            self.assertEqual(before.status_code,200,before.text)
            self.assertEqual(before.json()["reviews"],[])
            self.assertEqual(before.json()["review_version"],0)
            decision=self._review(self.req_id,"confirmed")
            self.assertEqual(decision.status_code,200,decision.text)
            history=self.client.get(url,headers={"Authorization":f"Bearer {self.token}"})
            self.assertEqual(history.status_code,200,history.text)
            self.assertEqual(history.json()["approval_state"],"confirmed")
            self.assertEqual(history.json()["review_version"],1)
            self.assertEqual(len(history.json()["reviews"]),1)
            item=history.json()["reviews"][0]
            self.assertEqual((item["version"],item["next_state"],item["previous_state"]),
                             (1,"confirmed","proposed"))
            self.assertEqual(item["reviewer_id"],str(self.ia))
            self.assertEqual(item["rationale"],"Reviewed supporting evidence")
            self.assertIn("reviewed_at",item)
        finally:
            self.db.execute("DELETE FROM sme.discovery_change_events "
                            "WHERE tenant_id=%s AND subject_id=%s AND action='requirement.reviewed'",
                            (self.a,self.req_id))
            self.db.execute("DELETE FROM sme.discovery_requirement_reviews "
                            "WHERE tenant_id=%s AND requirement_id=%s",(self.a,self.req_id))
            self.db.execute("UPDATE sme.discovery_requirements "
                            "SET approval_state='proposed',review_version=0 "
                            "WHERE tenant_id=%s AND id=%s",(self.a,self.req_id))
            self._restore_viewer()

    def test_review_history_viewer_wrong_tenant_and_unknown_denied(self):
        endpoint=f"/v1/tenants/{self.a}/research-cases/{self.ca}/requirements/{self.req_id}/reviews"
        headers={"Authorization":f"Bearer {self.token}"}
        self.assertEqual(self.client.get(endpoint,headers=headers).status_code,403)
        self.assertEqual(self.client.get(endpoint).status_code,401)
        self._with_manager()
        try:
            wrong=f"/v1/tenants/{self.b}/research-cases/{self.cb}/requirements/{self.req_id}/reviews"
            self.assertEqual(self.client.get(wrong,headers=headers).status_code,403)
            missing=f"/v1/tenants/{self.a}/research-cases/{self.ca}/requirements/{uuid4()}/reviews"
            self.assertEqual(self.client.get(missing,headers=headers).status_code,403)
        finally:
            self._restore_viewer()

    def test_runtime_cannot_select_review_history_table_directly(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.db.transaction():
                self.db.execute("SET LOCAL ROLE sme_app")
                self.db.execute("SELECT rationale FROM sme.discovery_requirement_reviews")

    def test_site_picker_only_write_authorized_scope(self):
        endpoint=f"/v1/tenants/{self.a}/discovery-sites"
        headers={"Authorization":f"Bearer {self.token}"}
        # Viewing cases never implicitly grants the ability to create cases.
        denied=self.client.get(endpoint,headers=headers)
        self.assertEqual(denied.status_code,200,denied.text)
        self.assertEqual(denied.json()["sites"],[])
        self._with_manager()
        other_site=uuid4()
        self.db.execute("INSERT INTO sme.sites(tenant_id,id,label) "
                        "VALUES (%s,%s,'Restricted site')",(self.a,other_site))
        try:
            page=self.client.get(endpoint,headers=headers,params={"limit":1})
            self.assertEqual(page.status_code,200,page.text)
            self.assertEqual(page.json()["sites"],[{"id":str(self.sa),"label":"A site"}])
            self.assertIsNone(page.json()["next_cursor"])
            self.assertNotIn(str(other_site),str(page.json()))
            self.assertEqual(self.client.get(
                f"/v1/tenants/{self.b}/discovery-sites",headers=headers).status_code,403)
            self.assertEqual(self.client.get(endpoint).status_code,401)
            for params in ({"limit":0},{"limit":101},{"after":"bogus"}):
                self.assertEqual(self.client.get(
                    endpoint,params=params,headers=headers).status_code,422)
        finally:
            self.db.execute("DELETE FROM sme.sites WHERE tenant_id=%s AND id=%s",
                            (self.a,other_site))
            self._restore_viewer()

    def test_tenant_manager_site_picker_keyset_pagination(self):
        second=uuid4()
        self.db.execute("INSERT INTO sme.sites(tenant_id,id,label) "
                        "VALUES (%s,%s,'Site two')",(self.a,second))
        self.db.execute("DELETE FROM sme.role_assignments WHERE tenant_id=%s AND identity_id=%s",
                        (self.a,self.ia))
        self.db.execute("INSERT INTO sme.role_assignments "
                        "(tenant_id,id,identity_id,role,scope_type) "
                        "VALUES (%s,%s,%s,'manager','tenant')",
                        (self.a,uuid4(),self.ia))
        try:
            endpoint=f"/v1/tenants/{self.a}/discovery-sites"
            headers={"Authorization":f"Bearer {self.token}"}
            first=self.client.get(endpoint,headers=headers,params={"limit":1})
            self.assertEqual(first.status_code,200,first.text)
            self.assertIsNotNone(first.json()["next_cursor"])
            second_page=self.client.get(endpoint,headers=headers,params={
                "limit":1,"after":first.json()["next_cursor"]})
            self.assertEqual(second_page.status_code,200,second_page.text)
            self.assertIsNone(second_page.json()["next_cursor"])
            ids={first.json()["sites"][0]["id"],second_page.json()["sites"][0]["id"]}
            self.assertEqual(ids,{str(self.sa),str(second)})
        finally:
            self.db.execute("DELETE FROM sme.sites WHERE tenant_id=%s AND id=%s",
                            (self.a,second))
            self._restore_viewer()

    def test_source_list_existing_case_read_role_and_pagination(self):
        second=uuid4()
        self.db.execute("INSERT INTO sme.discovery_sources "
                        "(tenant_id,id,case_id,document_label,source_page) "
                        "VALUES (%s,%s,%s,'Second reference',9)",
                        (self.a,second,self.ca))
        try:
            endpoint=f"/v1/tenants/{self.a}/research-cases/{self.ca}/sources"
            headers={"Authorization":f"Bearer {self.token}"}
            first=self.client.get(endpoint,headers=headers,params={"limit":1})
            self.assertEqual(first.status_code,200,first.text)
            self.assertIsNotNone(first.json()["next_cursor"])
            second_page=self.client.get(endpoint,headers=headers,params={
                "limit":1,"after":first.json()["next_cursor"]})
            self.assertEqual(second_page.status_code,200,second_page.text)
            self.assertIsNone(second_page.json()["next_cursor"])
            both=first.json()["sources"]+second_page.json()["sources"]
            self.assertEqual({x["id"] for x in both},{str(self.source),str(second)})
            self.assertEqual({x["page"] for x in both},{1,9})
            self.assertEqual(self.client.get(endpoint).status_code,401)
            self.assertEqual(self.client.get(
                f"/v1/tenants/{self.b}/research-cases/{self.cb}/sources",
                headers=headers).status_code,403)
            for params in ({"limit":0},{"limit":101},{"after":"invalid"}):
                self.assertEqual(self.client.get(
                    endpoint,params=params,headers=headers).status_code,422)
        finally:
            self.db.execute("DELETE FROM sme.discovery_sources WHERE tenant_id=%s AND id=%s",
                            (self.a,second))

    def test_source_list_hidden_site_is_404_not_metadata_leak(self):
        other_site,other_case,other_source=uuid4(),uuid4(),uuid4()
        self.db.execute("INSERT INTO sme.sites(tenant_id,id,label) VALUES (%s,%s,'Hidden')",
                        (self.a,other_site))
        self.db.execute("INSERT INTO sme.discovery_cases "
                        "(tenant_id,id,site_id,label,company_code) "
                        "VALUES (%s,%s,%s,'Hidden project','OTHER')",
                        (self.a,other_case,other_site))
        self.db.execute("INSERT INTO sme.discovery_sources "
                        "(tenant_id,id,case_id,document_label,source_page) "
                        "VALUES (%s,%s,%s,'Restricted source',1)",
                        (self.a,other_source,other_case))
        self._with_manager()
        try:
            headers={"Authorization":f"Bearer {self.token}"}
            hidden=self.client.get(
                f"/v1/tenants/{self.a}/research-cases/{other_case}/sources",
                headers=headers)
            self.assertEqual(hidden.status_code,404,hidden.text)
            allowed=self.client.get(
                f"/v1/tenants/{self.a}/research-cases/{self.ca}/sources",
                headers=headers)
            self.assertEqual(allowed.status_code,200,allowed.text)
            self.assertNotIn("Restricted source",allowed.text)
        finally:
            self._restore_viewer()
            self.db.execute("DELETE FROM sme.discovery_sources WHERE tenant_id=%s AND id=%s",
                            (self.a,other_source))
            self.db.execute("DELETE FROM sme.discovery_cases WHERE tenant_id=%s AND id=%s",
                            (self.a,other_case))
            self.db.execute("DELETE FROM sme.sites WHERE tenant_id=%s AND id=%s",
                            (self.a,other_site))

    def test_cookie_bff_session_tenant_scope_and_csrf(self):
        from sme_partner.discovery_bff import create_cookie_discovery_app
        from fastapi.testclient import TestClient
        app=create_cookie_discovery_app(
            lambda: psycopg.connect(DSN),
            csrf_secret=b"synthetic-ci-only-csrf-secret-not-for-customer!",
            trusted_origin="https://pilot.test"
        )
        token=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
        sid=uuid4()
        self.db.execute("INSERT INTO sme.sessions(id,identity_id,token_digest,expires_at) "
                        "VALUES (%s,%s,%s,%s)",(sid,self.ia,hashlib.sha256(token.encode()).digest(),
                        datetime.now(timezone.utc)+timedelta(hours=1)))
        try:
            with TestClient(app,base_url="https://pilot.test",follow_redirects=False) as browser:
                self.assertEqual(browser.get("/auth/session/tenants").status_code,401)
                # An untrusted Authorization header never substitutes for session cookies.
                self.assertEqual(browser.get("/v1/tenants/%s/research-cases" % self.a,
                    headers={"Authorization":f"Bearer {token}"}).status_code,401)
                browser.cookies.set("__Host-sme_session",token,domain="pilot.test",path="/")
                t=browser.get("/auth/session/tenants")
                self.assertEqual(t.status_code,200,t.text)
                self.assertEqual(t.json()["tenants"],[{"id":str(self.a),"label":"Research A"}])
                self.assertNotIn(token,t.text)
                csrf=t.json()["csrf_token"]
                self.assertEqual(len(csrf),64)
                cases=browser.get(f"/v1/tenants/{self.a}/research-cases")
                self.assertEqual(cases.status_code,200,cases.text)
                self.assertEqual(len(cases.json()["cases"]),1)
                self.assertEqual(browser.get(
                    f"/v1/tenants/{self.b}/research-cases").status_code,403)
                self.assertEqual(browser.get("/v1/session/logout").status_code,404)
                self.assertEqual(browser.post("/auth/session/logout").status_code,403)
                self.assertEqual(browser.post("/auth/session/logout",headers={
                    "Origin":"https://attacker.example","X-CSRF-Token":csrf
                }).status_code,403)
                self.assertEqual(browser.post("/auth/session/logout",headers={
                    "Origin":"https://pilot.test","X-CSRF-Token":"0"*64
                }).status_code,403)
                self.assertEqual(browser.post("/auth/session/logout",headers={
                    "Origin":"https://pilot.test","X-CSRF-Token":csrf,
                    "Authorization":f"Bearer {token}"
                }).status_code,400)
                # State remains active after all failed attempts; logout requires both signals.
                self.assertEqual(browser.get("/auth/session/tenants").status_code,200)
                result=browser.post("/auth/session/logout",headers={
                    "Origin":"https://pilot.test","X-CSRF-Token":csrf
                })
                self.assertEqual(result.status_code,204,result.text)
                self.assertIn("Max-Age=0",result.headers.get("set-cookie",""))
                self.assertEqual(browser.get("/auth/session/tenants").status_code,401)

        finally:
            self.db.execute("DELETE FROM sme.sessions WHERE id=%s",(sid,))

    def test_cookie_bff_scope_revocation_and_no_forged_tenant(self):
        from sme_partner.discovery_bff import create_cookie_discovery_app
        from fastapi.testclient import TestClient
        browser_app=create_cookie_discovery_app(
            lambda: psycopg.connect(DSN),
            csrf_secret=b"synthetic-ci-only-csrf-secret-not-for-customer!",
            trusted_origin="https://pilot.test"
        )
        # Fresh independent login token to avoid mutations across tests.
        token=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
        sid=uuid4()
        self.db.execute("INSERT INTO sme.sessions(id,identity_id,token_digest,expires_at) "
                        "VALUES (%s,%s,%s,%s)",(sid,self.ia,hashlib.sha256(token.encode()).digest(),
                        datetime.now(timezone.utc)+timedelta(hours=1)))
        try:
            with TestClient(browser_app,base_url="https://pilot.test") as browser:
                browser.cookies.set("__Host-sme_session",token,domain="pilot.test",path="/")
                self.assertEqual(browser.get("/auth/session/tenants").status_code,200)
                self.db.execute("UPDATE sme.memberships SET status='disabled' "
                                "WHERE tenant_id=%s AND identity_id=%s",(self.a,self.ia))
                self.assertEqual(browser.get("/auth/session/tenants").status_code,401)
                self.assertEqual(browser.get(
                    f"/v1/tenants/{self.a}/research-cases").status_code,403)
        finally:
            self.db.execute("UPDATE sme.memberships SET status='active' "
                            "WHERE tenant_id=%s AND identity_id=%s",(self.a,self.ia))
            self.db.execute("DELETE FROM sme.sessions WHERE id=%s",(sid,))

    def test_cookie_bff_config_is_fail_closed(self):
        from sme_partner.discovery_bff import create_cookie_discovery_app
        for origin in ("http://pilot.test","https://pilot.test/unsafe",
                       "https://pilot.test?x=1","https://user@pilot.test"):
            with self.subTest(origin=origin),self.assertRaises(ValueError):
                create_cookie_discovery_app(lambda:None,csrf_secret=b"x"*32,
                                             trusted_origin=origin)
        with self.assertRaises(ValueError):
            create_cookie_discovery_app(lambda:None,csrf_secret=b"weak",trusted_origin="https://pilot.test")

    def test_cookie_bff_post_requires_csrf_and_preserves_db_idempotency(self):
        from sme_partner.discovery_bff import create_cookie_discovery_app
        from fastapi.testclient import TestClient
        token=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
        sid=uuid4()
        key=secrets.token_urlsafe(24)
        created=None
        self.db.execute("INSERT INTO sme.sessions(id,identity_id,token_digest,expires_at) "
                        "VALUES (%s,%s,%s,%s)",(sid,self.ia,hashlib.sha256(token.encode()).digest(),
                        datetime.now(timezone.utc)+timedelta(hours=1)))
        self._with_manager()
        try:
            app=create_cookie_discovery_app(
                lambda: psycopg.connect(DSN),csrf_secret=b"synthetic-cookie-bff-test-secret-12345",
                trusted_origin="https://pilot.test")
            with TestClient(app,base_url="https://pilot.test") as browser:
                browser.cookies.set("__Host-sme_session",token,domain="pilot.test",path="/")
                bootstrap=browser.get("/auth/session/tenants")
                self.assertEqual(bootstrap.status_code,200,bootstrap.text)
                csrf=bootstrap.json()["csrf_token"]
                url=f"/v1/tenants/{self.a}/research-cases"
                payload={"site_id":str(self.sa),"label":"Cookie BFF synthetic case",
                         "company_code":"OTHER"}
                headers={"Idempotency-Key":key}
                self.assertEqual(browser.post(url,json=payload,headers=headers).status_code,403)
                self.assertEqual(browser.post(url,json=payload,headers={
                    **headers,"Origin":"https://attacker.example",
                    "X-CSRF-Token":csrf}).status_code,403)
                self.assertEqual(browser.post(url,json=payload,headers={
                    **headers,"Origin":"https://pilot.test",
                    "X-CSRF-Token":"wrong"}).status_code,403)
                valid={**headers,"Origin":"https://pilot.test","X-CSRF-Token":csrf}
                first=browser.post(url,json=payload,headers=valid)
                self.assertEqual(first.status_code,201,first.text)
                created=first.json()["case_id"]
                second=browser.post(url,json=payload,headers=valid)
                self.assertEqual(second.status_code,200,second.text)
                self.assertEqual(second.json()["case_id"],created)
                self.assertTrue(second.json()["replayed"])
                self.assertEqual(self.db.execute(
                    "SELECT count(*) FROM sme.discovery_change_events "
                    "WHERE tenant_id=%s AND case_id=%s",(self.a,created)).fetchone()[0],1)
        finally:
            if created:
                self.db.execute("DELETE FROM sme.discovery_create_requests "
                                "WHERE tenant_id=%s AND case_id=%s",(self.a,created))
                self.db.execute("DELETE FROM sme.discovery_change_events "
                                "WHERE tenant_id=%s AND case_id=%s",(self.a,created))
                self.db.execute("DELETE FROM sme.discovery_cases "
                                "WHERE tenant_id=%s AND id=%s",(self.a,created))
            self._restore_viewer()
            self.db.execute("DELETE FROM sme.sessions WHERE id=%s",(sid,))

    def test_cookie_bff_oidc_bridge_issues_cookie_then_reads_tenant(self):
        from sme_partner.discovery_bff import create_cookie_discovery_app
        from sme_partner.oidc_flow import LoginStart, LoginRejected
        from fastapi.testclient import TestClient
        token=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
        sid=uuid4()
        self.db.execute("INSERT INTO sme.sessions(id,identity_id,token_digest,expires_at) "
                        "VALUES (%s,%s,%s,%s)",(sid,self.ia,hashlib.sha256(token.encode()).digest(),
                        datetime.now(timezone.utc)+timedelta(hours=1)))
        class SyntheticFlow:
            settings=type("Settings",(),{"session_lifetime_seconds":3600})()
            binding=secrets.token_urlsafe(32)
            state=secrets.token_urlsafe(32)
            done=False
            def start(self):
                return LoginStart("https://id.synthetic.test/authorize?state="+self.state,
                                  self.state,self.binding)
            def complete(self,*,state,browser_binding,code):
                if (self.done or state!=self.state or browser_binding!=self.binding
                        or code!="synthetic-code"):
                    raise LoginRejected("invalid")
                self.done=True
                return token
        try:
            app=create_cookie_discovery_app(lambda:psycopg.connect(DSN),
                csrf_secret=b"synthetic-cookie-oidc-gateway-test-secret",
                trusted_origin="https://pilot.test",oidc_flow=SyntheticFlow())
            with TestClient(app,base_url="https://pilot.test",follow_redirects=False) as browser:
                self.assertEqual(browser.get("/auth/session/tenants").status_code,401)
                start=browser.get("/auth/oidc/start")
                self.assertEqual(start.status_code,302,start.text)
                self.assertIn("__Host-sme_oidc_binding",start.headers["set-cookie"])
                flow_state=start.headers["location"].split("state=")[1]
                callback=browser.get("/auth/oidc/callback",params={
                    "state":flow_state,"code":"synthetic-code"})
                self.assertEqual(callback.status_code,303,callback.text)
                self.assertEqual(callback.headers["location"],"/")
                self.assertIn("__Host-sme_session",callback.headers["set-cookie"])
                self.assertNotIn(token,callback.headers["location"])
                tenant=browser.get("/auth/session/tenants")
                self.assertEqual(tenant.status_code,200,tenant.text)
                self.assertEqual(tenant.json()["tenants"][0]["id"],str(self.a))
                self.assertEqual(browser.get("/v1/tenants/%s/research-cases" %
                                             self.a).status_code,200)
                self.assertEqual(browser.get("/auth/oidc/callback",params={
                    "state":flow_state,"code":"synthetic-code"}).status_code,401)
        finally:
            self.db.execute("DELETE FROM sme.sessions WHERE id=%s",(sid,))
