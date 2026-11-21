"""Real PostgreSQL API E2E tests, no customer database or production keys."""
import base64
import hashlib
import os
import secrets
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

try:
    import psycopg
    from fastapi.testclient import TestClient
    from sme_partner.session_api import create_app
except ImportError:
    psycopg = None
    TestClient = None

DSN = os.getenv("SME_TEST_DATABASE_DSN")
ROOT = Path(__file__).resolve().parents[1]


def _token():
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")


@unittest.skipUnless(DSN and psycopg and TestClient, "Requires disposable Postgres, FastAPI and httpx")
class SessionApiE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin = psycopg.connect(DSN, autocommit=True)
        for name in ("0001_tenant_foundation.sql", "0002_scoped_rbac.sql", "0003_session_boundary.sql", "0005_security_audit.sql", "0006_tenant_selector.sql", "0007_membership_least_privilege.sql"):
            cls.admin.execute((ROOT / "migrations" / name).read_text())
        cls.a,cls.b,cls.user,cls.other,cls.site_a,cls.site_b,cls.asset_a,cls.asset_b = (uuid4() for _ in range(8))
        cls.token = _token()
        cls.other_token = _token()
        cls.expired_token = _token()
        cls.revoked_token = _token()
        now = datetime.now(timezone.utc)
        cls.admin.execute("INSERT INTO sme.tenants(id,slug,display_name) VALUES (%s,%s,'Company A'),(%s,%s,'Company B')",
                          (cls.a,'api-'+cls.a.hex[:12],cls.b,'api-'+cls.b.hex[:12]))
        cls.admin.execute("INSERT INTO sme.identities(id,issuer,subject) VALUES (%s,'https://id.example',%s),(%s,'https://id.example',%s)",
                          (cls.user,cls.user.hex,cls.other,cls.other.hex))
        cls.admin.execute("INSERT INTO sme.memberships(tenant_id,identity_id,status) VALUES (%s,%s,'active'),(%s,%s,'active')",
                          (cls.a,cls.user,cls.b,cls.other))
        cls.admin.execute("INSERT INTO sme.sites(tenant_id,id,label) VALUES (%s,%s,'A'),(%s,%s,'B')",
                          (cls.a,cls.site_a,cls.b,cls.site_b))
        cls.admin.execute("INSERT INTO sme.assets(tenant_id,id,site_id,name) VALUES (%s,%s,%s,'Asset A'),(%s,%s,%s,'Asset B')",
                          (cls.a,cls.asset_a,cls.site_a,cls.b,cls.asset_b,cls.site_b))
        cls.admin.execute(
            "INSERT INTO sme.role_assignments(tenant_id,id,identity_id,role,scope_type) "
            "VALUES (%s,%s,%s,'viewer','tenant'),(%s,%s,%s,'viewer','tenant')",
            (cls.a,uuid4(),cls.user,cls.b,uuid4(),cls.other))
        for identity,token,expiry,revoked in [
            (cls.user,cls.token,now+timedelta(hours=1),None),
            (cls.other,cls.other_token,now+timedelta(hours=1),None),
            (cls.user,cls.expired_token,now-timedelta(seconds=1),None),
            (cls.user,cls.revoked_token,now+timedelta(hours=1),now),
        ]:
            cls.admin.execute(
                "INSERT INTO sme.sessions(id,identity_id,token_digest,created_at,expires_at,revoked_at) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (uuid4(),identity,hashlib.sha256(token.encode('ascii')).digest(),
                 now-timedelta(hours=2), expiry,revoked))
        cls.client = TestClient(create_app(lambda: psycopg.connect(DSN)))

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.admin.close()

    def get_assets(self,tenant,token=None):
        return self.client.get(
            f"/v1/tenants/{tenant}/assets",
            headers={"Authorization":f"Bearer {token}"} if token else {},
        )

    def test_browser_cookie_can_read_authorized_tenant(self):
        r=self.client.get(f"/v1/tenants/{self.a}/assets",
            headers={"Cookie":f"__Host-sme_session={self.token}"})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual([x["name"] for x in r.json()["assets"]],["Asset A"])

    def test_browser_cookie_cannot_switch_to_foreign_tenant(self):
        r=self.client.get(f"/v1/tenants/{self.b}/assets",
            headers={"Cookie":f"__Host-sme_session={self.token}"})
        self.assertEqual(r.status_code,403)

    def test_tenant_selector_lists_only_active_membership(self):
        r=self.client.get("/v1/me/tenants",
            headers={"Cookie":f"__Host-sme_session={self.token}"})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual([v["id"] for v in r.json()["tenants"]],[str(self.a)])

    def test_tenant_selector_rejects_unknown_token(self):
        r=self.client.get("/v1/me/tenants",
            headers={"Cookie":f"__Host-sme_session={_token()}"})
        self.assertEqual(r.status_code,403)

    def test_valid_tenant_returns_only_its_asset(self):
        r=self.get_assets(self.a,self.token)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual([x["name"] for x in r.json()["assets"]],["Asset A"])

    def test_second_tenant_returns_only_its_asset(self):
        r=self.get_assets(self.b,self.other_token)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual([x["name"] for x in r.json()["assets"]],["Asset B"])

    def test_wrong_tenant_denied(self):
        self.assertEqual(self.get_assets(self.b,self.token).status_code,403)

    def test_missing_token_denied(self):
        self.assertEqual(self.get_assets(self.a).status_code,401)

    def test_forged_token_denied(self):
        self.assertEqual(self.get_assets(self.a,_token()).status_code,403)

    def test_expired_session_denied(self):
        self.assertEqual(self.get_assets(self.a,self.expired_token).status_code,403)

    def test_revoked_session_denied(self):
        self.assertEqual(self.get_assets(self.a,self.revoked_token).status_code,403)

    def test_disabled_membership_denied(self):
        self.admin.execute("UPDATE sme.memberships SET status='disabled' WHERE tenant_id=%s AND identity_id=%s",(self.a,self.user))
        try:
            self.assertEqual(self.get_assets(self.a,self.token).status_code,403)
        finally:
            self.admin.execute("UPDATE sme.memberships SET status='active' WHERE tenant_id=%s AND identity_id=%s",(self.a,self.user))

    def test_suspended_tenant_denied(self):
        self.admin.execute("UPDATE sme.tenants SET status='suspended' WHERE id=%s",(self.a,))
        try:
            self.assertEqual(self.get_assets(self.a,self.token).status_code,403)
        finally:
            self.admin.execute("UPDATE sme.tenants SET status='active' WHERE id=%s",(self.a,))

    def test_role_revocation_removes_asset_visibility(self):
        self.admin.execute("DELETE FROM sme.role_assignments WHERE tenant_id=%s AND identity_id=%s",(self.a,self.user))
        try:
            r=self.get_assets(self.a,self.token)
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.json()["assets"],[])
        finally:
            self.admin.execute(
                "INSERT INTO sme.role_assignments(tenant_id,id,identity_id,role,scope_type) VALUES (%s,%s,%s,'viewer','tenant')",
                (self.a,uuid4(),self.user))

    def test_logout_revokes_session(self):
        token=_token()
        self.admin.execute(
            "INSERT INTO sme.sessions(id,identity_id,token_digest,expires_at) VALUES (%s,%s,%s,%s)",
            (uuid4(),self.user,hashlib.sha256(token.encode()).digest(),
             datetime.now(timezone.utc)+timedelta(hours=1)))
        r=self.client.post('/v1/session/logout',headers={'Authorization':f'Bearer {token}'})
        self.assertEqual(r.status_code,204)
        self.assertEqual(self.get_assets(self.a,token).status_code,403)

    def test_asset_list_creates_tenant_audit(self):
        before=self.admin.execute("SELECT count(*) FROM sme.security_audit WHERE tenant_id=%s",(self.a,)).fetchone()[0]
        self.assertEqual(self.get_assets(self.a,self.token).status_code,200)
        after=self.admin.execute("SELECT count(*) FROM sme.security_audit WHERE tenant_id=%s",(self.a,)).fetchone()[0]
        self.assertEqual(after,before+1)

    def test_cross_tenant_audit_denied(self):
        from uuid import uuid4
        import hashlib
        with self.admin.transaction():
            self.admin.execute("SET LOCAL ROLE sme_app")
            result=self.admin.execute(
                "SELECT sme.record_session_audit(%s,%s,'asset.list','asset',%s)",
                (hashlib.sha256(self.token.encode()).digest(),self.b,uuid4())
            ).fetchone()[0]
            self.assertFalse(result)

    def test_runtime_cannot_self_enroll_membership(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.admin.transaction():
                self.admin.execute("SET LOCAL ROLE sme_app")
                self.admin.execute("SELECT set_config('sme.tenant_id',%s,true)",(str(self.b),))
                self.admin.execute(
                    "INSERT INTO sme.memberships(tenant_id,identity_id,status) VALUES (%s,%s,'active')",
                    (self.b,self.user))

    def test_runtime_cannot_change_membership(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.admin.transaction():
                self.admin.execute("SET LOCAL ROLE sme_app")
                self.admin.execute("SELECT set_config('sme.tenant_id',%s,true)",(str(self.a),))
                self.admin.execute(
                    "UPDATE sme.memberships SET status='active' WHERE tenant_id=%s AND identity_id=%s",
                    (self.a,self.user))

    def test_runtime_cannot_delete_membership(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.admin.transaction():
                self.admin.execute("SET LOCAL ROLE sme_app")
                self.admin.execute("SELECT set_config('sme.tenant_id',%s,true)",(str(self.a),))
                self.admin.execute("DELETE FROM sme.memberships WHERE tenant_id=%s",(self.a,))

    def test_runtime_cannot_mutate_audit(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.admin.transaction():
                self.admin.execute("SET LOCAL ROLE sme_app")
                self.admin.execute("DELETE FROM sme.security_audit")

    def test_runtime_cannot_read_session_table(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.admin.transaction():
                self.admin.execute("SET LOCAL ROLE sme_app")
                self.admin.execute("SELECT token_digest FROM sme.sessions").fetchall()
