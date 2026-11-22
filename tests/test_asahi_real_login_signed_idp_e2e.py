"""Spec 026: real PostgreSQL login isolation + signed synthetic IdP + HTTPS TestClient.

Test-only credentials and RSA keys are ephemeral. No external IdP, no real
network/TLS ingress, and no actual outgoing notification is exercised.
"""
import json
import os
import secrets
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm

try:
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
except ImportError:
    psycopg = None

from sme_partner.asahi_stepup_approval import PostgresApprovalExecutor
from sme_partner.asahi_stepup_bff import install_asahi_stepup_bff
from sme_partner.asahi_stepup_oidc_flow import AsahiStepupOIDCFlow, PostgresStepupStore
from sme_partner.browser_gateway import SESSION_COOKIE, _session_csrf
from sme_partner.oidc import OIDCConfig
from sme_partner.oidc_flow import OIDCLoginSettings, _digest


DSN = os.getenv("SME_TEST_DATABASE_DSN")
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(DSN and psycopg, "disposable PostgreSQL required")
class SignedIdPRealLoginAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin = psycopg.connect(DSN, autocommit=True)
        for migration in sorted((ROOT / "migrations").glob("*.sql")):
            cls.admin.execute(migration.read_text())
        cls.issuer_password = secrets.token_urlsafe(32)
        cls.approval_password = secrets.token_urlsafe(32)
        for role, inherited, password in (
            ("sme_stepup_e2e_login", "sme_stepup", cls.issuer_password),
            ("sme_approval_e2e_login", "sme_approval", cls.approval_password),
        ):
            cls.admin.execute(
                "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='"
                + role + "') THEN CREATE ROLE " + role
                + " LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS; "
                "END IF; END $$"
            )
            # Passwords are parameters; never write or log them.
            from psycopg import sql
            cls.admin.execute(
                sql.SQL("ALTER ROLE {} WITH LOGIN INHERIT PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
            cls.admin.execute(
                sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(inherited), sql.Identifier(role)
                )
            )
            cls.admin.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(conninfo_to_dict(DSN)["dbname"]), sql.Identifier(role)
                )
            )
        cls.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = json.loads(RSAAlgorithm.to_jwk(cls.private.public_key()))
        jwk.update({"kid":"trusted-idp-test","alg":"RS256","use":"sig"})
        cls.oidc = OIDCConfig("https://id.example","sme-web",{"keys":[jwk]})
        cls.csrf_key = secrets.token_bytes(32)

    @classmethod
    def tearDownClass(cls):
        cls.admin.close()

    @classmethod
    def login(cls, name, password):
        # These are actual authenticated TCP logins, never SET ROLE as admin.
        config=conninfo_to_dict(DSN)
        config.update(user=name,password=password)
        return psycopg.connect(**config)

    def issuer_connect(self):
        return self.login("sme_stepup_e2e_login",self.issuer_password)

    def approval_connect(self):
        return self.login("sme_approval_e2e_login",self.approval_password)

    def setUp(self):
        self.tenant=uuid4()
        self.identity=uuid4()
        self.token=secrets.token_urlsafe(32)
        self.subject=self.identity.hex
        self.admin.execute(
            "INSERT INTO sme.tenants(id,slug,display_name) VALUES(%s,%s,'Spec 026')",
            (self.tenant,"e2e-"+self.tenant.hex[:14])
        )
        self.admin.execute(
            "INSERT INTO sme.identities(id,issuer,subject) VALUES(%s,%s,%s)",
            (self.identity,"https://id.example",self.subject)
        )
        self.admin.execute(
            "INSERT INTO sme.memberships(tenant_id,identity_id) VALUES(%s,%s)",
            (self.tenant,self.identity)
        )
        self.admin.execute(
            "INSERT INTO sme.sessions(id,identity_id,token_digest,expires_at)"
            " VALUES(%s,%s,%s,%s)",
            (uuid4(),self.identity,_digest(self.token),
             datetime.now(timezone.utc)+timedelta(hours=1))
        )
        self.admin.execute(
            "INSERT INTO sme.role_assignments(id,tenant_id,identity_id,role,scope_type)"
            " VALUES(%s,%s,%s,'owner','tenant')",
            (uuid4(),self.tenant,self.identity)
        )
        self.nonce=None
        self.override={}
        self.exchange_count=0
        def exchange(code,verifier,redirect,client):
            self.exchange_count+=1
            self.assertEqual(code,"synthetic-idp-code-012345")
            self.assertEqual(redirect,"https://app.example/auth/asahi/stepup/callback")
            self.assertEqual(client,"sme-web")
            now=int(datetime.now(timezone.utc).timestamp())
            claims={"iss":"https://id.example","sub":self.subject,"aud":"sme-web",
                    "iat":now,"exp":now+240,"auth_time":now-5,
                    "nonce":self.nonce,"amr":["pwd","otp"]}
            claims.update(self.override)
            return jwt.encode(claims,self.private,algorithm="RS256",
                              headers={"kid":"trusted-idp-test"})
        settings=OIDCLoginSettings(
            "https://id.example/authorize",
            "https://app.example/auth/asahi/stepup/callback",
            self.oidc
        )
        self.store=PostgresStepupStore(self.issuer_connect)
        self.flow=AsahiStepupOIDCFlow(settings,self.store,exchange)
        self.app=FastAPI()
        def active(token):
            return bool(self.admin.execute(
                "SELECT EXISTS(SELECT 1 FROM sme.sessions WHERE token_digest=%s"
                " AND revoked_at IS NULL AND expires_at>now())",
                (_digest(token),)
            ).fetchone()[0])
        install_asahi_stepup_bff(
            self.app,self.flow,public_origin="https://app.example",
            csrf_key=self.csrf_key,session_active=active,
            apply_proof=PostgresApprovalExecutor(self.approval_connect),
            enabled=True,
            # Integration TEST bypasses production infrastructure preflight.
            # This must never be reused as a production deployment recipe.
            production_preflight=lambda: None
        )
        self.client=TestClient(self.app,base_url="https://app.example",
                               follow_redirects=False)
        self.client.cookies.set(SESSION_COOKIE,self.token,domain="app.example",path="/")

    def start(self, action="approve", tenant=None, ref="tenant/alerts"):
        payload={"action":action}
        if action=="approve":
            payload.update(channel="email",destination_ref=ref,
                           secret_ref="tenant/secret")
        response=self.client.post(
            f"/v1/tenants/{tenant or self.tenant}/itops/asahi/stepup/start",
            json=payload,headers={
                "Origin":"https://app.example",
                "X-CSRF-Token":_session_csrf(self.token,self.csrf_key)
            }
        )
        return response

    def callback(self, response, **params):
        data=parse_qs(urlsplit(response.headers["location"]).query)
        self.nonce=data["nonce"][0]
        query={"state":data["state"][0],"code":"synthetic-idp-code-012345"}
        query.update(params)
        return self.client.get("/auth/asahi/stepup/callback",params=query)

    def audit_operations(self):
        return [r[0] for r in self.admin.execute(
            "SELECT operation FROM sme.asahi_delivery_policy_audit WHERE tenant_id=%s"
            " ORDER BY id",(self.tenant,)
        ).fetchall()]

    def test_signed_fresh_mfa_approve_revoke_and_audit_via_two_real_db_logins(self):
        started=self.start()
        self.assertEqual(started.status_code,303,started.text)
        self.assertEqual(self.callback(started).status_code,303)
        self.assertEqual(self.audit_operations(),["created"])
        row=self.admin.execute(
            "SELECT enabled,approved_by FROM sme.asahi_delivery_destinations"
            " WHERE tenant_id=%s",(self.tenant,)
        ).fetchone()
        self.assertEqual(row,(True,self.identity))
        revoke=self.start("revoke")
        self.assertEqual(revoke.status_code,303)
        self.assertEqual(self.callback(revoke).status_code,303)
        self.assertEqual(self.audit_operations(),["created","revoked"])
        self.assertEqual(self.admin.execute(
            "SELECT enabled FROM sme.asahi_delivery_destinations WHERE tenant_id=%s",
            (self.tenant,)
        ).fetchone(),(False,))

    def test_invalid_mfa_is_consumed_and_cannot_create_audit(self):
        started=self.start()
        self.override={"amr":["pwd"]}
        self.assertEqual(self.callback(started).status_code,403)
        self.assertEqual(self.audit_operations(),[])
        # A new browser challenge is required after an MFA rejection.
        self.assertEqual(self.start().status_code,303)
        self.override={"auth_time":int(datetime.now(timezone.utc).timestamp())-500}
        latest=self.start()
        self.assertEqual(self.callback(latest).status_code,403)
        self.assertEqual(self.audit_operations(),[])

    def test_forged_callback_wrong_browser_and_tenant_denied(self):
        started=self.start()
        data=parse_qs(urlsplit(started.headers["location"]).query)
        self.assertEqual(self.client.get(
            "/auth/asahi/stepup/callback",
            params={"state":"x"*43,"code":"synthetic-idp-code-012345"}
        ).status_code,403)
        self.assertEqual(self.exchange_count,0)
        self.assertEqual(self.audit_operations(),[])
        # Cross-tenant owner challenge must not be issued.
        self.assertEqual(self.start(tenant=uuid4()).status_code,403)
        self.assertEqual(self.audit_operations(),[])

    def test_revocation_between_challenge_and_callback_prevents_proof(self):
        started=self.start()
        self.admin.execute(
            "UPDATE sme.sessions SET revoked_at=now() WHERE token_digest=%s",
            (_digest(self.token),)
        )
        self.assertEqual(self.callback(started).status_code,403)
        self.assertEqual(self.audit_operations(),[])

    def test_runtime_principals_prohibit_cross_role_escalation(self):
        with self.issuer_connect() as conn:
            self.assertEqual(conn.execute("SELECT session_user").fetchone()[0],
                             "sme_stepup_e2e_login")
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                conn.execute("SET ROLE sme_approval")
        with self.approval_connect() as conn:
            self.assertEqual(conn.execute("SELECT session_user").fetchone()[0],
                             "sme_approval_e2e_login")
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                conn.execute("SET ROLE sme_stepup")


if __name__=="__main__":
    unittest.main()
