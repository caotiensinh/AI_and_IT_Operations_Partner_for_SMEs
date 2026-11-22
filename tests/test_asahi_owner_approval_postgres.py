"""Spec 017 owner-only PostgreSQL verified-session approval regression."""
import os
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from uuid import uuid4

try:
    import psycopg
except ImportError:
    psycopg = None

DSN = os.getenv("SME_TEST_DATABASE_DSN")
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(DSN and psycopg, "requires disposable PostgreSQL")
class OwnerApprovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = psycopg.connect(DSN, autocommit=True)
        for path in sorted((ROOT / "migrations").glob("*.sql")):
            cls.db.execute(path.read_text())

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def setUp(self):
        self.tenant = uuid4()
        self.actor = uuid4()
        self.other = uuid4()
        self.digest = os.urandom(32)
        self.other_digest = os.urandom(32)
        self.db.execute(
            "INSERT INTO sme.tenants(id,slug,display_name) VALUES(%s,%s,'Approval')",
            (self.tenant, "ap-" + self.tenant.hex[:12]),
        )
        for identity, digest in ((self.actor,self.digest),(self.other,self.other_digest)):
            self.db.execute(
                "INSERT INTO sme.identities(id,issuer,subject) VALUES (%s,'test',%s)",
                (identity,identity.hex),
            )
            self.db.execute(
                "INSERT INTO sme.memberships(tenant_id,identity_id) VALUES(%s,%s)",
                (self.tenant,identity),
            )
            self.db.execute(
                "INSERT INTO sme.sessions(id,identity_id,token_digest,expires_at) VALUES(%s,%s,%s,%s)",
                (uuid4(),identity,digest,datetime.now(timezone.utc)+timedelta(hours=1)),
            )
        self.role_id = uuid4()
        self.db.execute(
            "INSERT INTO sme.role_assignments(tenant_id,id,identity_id,role,scope_type)"
            " VALUES(%s,%s,%s,'owner','tenant')",
            (self.tenant,self.role_id,self.actor),
        )

    def call(self, fn, *args, role="sme_approval"):
        with psycopg.connect(DSN) as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE " + role)
                placeholders = ",".join("%s" for _ in args)
                return conn.execute(
                    "SELECT sme." + fn + "(" + placeholders + ")",args
                ).fetchone()[0]

    def issue(self, action, digest, tenant, channel=None, destination=None, secret=None, lifetime=60):
        return self.call("issue_asahi_stepup", digest, tenant, action,
                         channel, destination, secret, lifetime, role="sme_stepup")

    def approve(self, digest=None, tenant=None, channel="email",
                destination="tenant/alerts", secret="tenant/secret", role="sme_approval"):
        digest = self.digest if digest is None else digest
        tenant = self.tenant if tenant is None else tenant
        if role != "sme_approval":
            return self.call("approve_asahi_delivery_stepup", digest, tenant, uuid4(),
                             channel, destination, secret, role=role)
        proof = self.issue("approve", digest, tenant, channel, destination, secret)
        return bool(proof) and self.call("approve_asahi_delivery_stepup", digest,
                                         tenant, proof, channel, destination, secret, role=role)

    def revoke(self, digest=None, tenant=None, role="sme_approval"):
        digest = self.digest if digest is None else digest
        tenant = self.tenant if tenant is None else tenant
        if role != "sme_approval":
            return self.call("revoke_asahi_delivery_stepup", digest, tenant, uuid4(), role=role)
        proof = self.issue("revoke", digest, tenant)
        return bool(proof) and self.call("revoke_asahi_delivery_stepup", digest,
                                         tenant, proof, role=role)

    def test_owner_approves_and_revokes_with_audit(self):
        self.assertTrue(self.approve())
        self.assertTrue(self.revoke())
        self.assertFalse(self.revoke())
        row = self.db.execute(
            "SELECT enabled,revoked_at,approved_by FROM sme.asahi_delivery_destinations"
            " WHERE tenant_id=%s",(self.tenant,),
        ).fetchone()
        self.assertFalse(row[0])
        self.assertIsNotNone(row[1])
        self.assertEqual(row[2],self.actor)
        actions = self.db.execute(
            "SELECT operation FROM sme.asahi_delivery_policy_audit"
            " WHERE tenant_id=%s ORDER BY id",(self.tenant,)
        ).fetchall()
        self.assertEqual(actions,[("created",),("revoked",)])

    def test_update_and_reapproval_produce_audit(self):
        self.assertTrue(self.approve())
        self.assertTrue(self.approve(channel="webhook",destination="tenant/hook"))
        self.assertTrue(self.revoke())
        self.assertTrue(self.approve())
        row = self.db.execute(
            "SELECT enabled,revoked_at,channel FROM sme.asahi_delivery_destinations"
            " WHERE tenant_id=%s",(self.tenant,)
        ).fetchone()
        self.assertEqual(row,(True,None,"email"))
        actions = self.db.execute(
            "SELECT operation FROM sme.asahi_delivery_policy_audit"
            " WHERE tenant_id=%s ORDER BY id",(self.tenant,)
        ).fetchall()
        self.assertEqual(actions,[("created",),("updated",),("revoked",),("updated",)])

    def test_nonowner_and_bad_digest_denied(self):
        self.assertFalse(self.approve(digest=self.other_digest))
        self.assertFalse(self.approve(digest=b"wrong"))
        self.assertFalse(self.approve(digest=os.urandom(32)))
        self.assertFalse(self.revoke(digest=self.other_digest))
        self.assertIsNone(self.db.execute(
            "SELECT enabled FROM sme.asahi_delivery_destinations WHERE tenant_id=%s",
            (self.tenant,),
        ).fetchone())

    def test_suspended_tenant_revoked_session_and_removed_owner_denied(self):
        self.db.execute("UPDATE sme.tenants SET status='suspended' WHERE id=%s",
                        (self.tenant,))
        self.assertFalse(self.approve())
        self.db.execute("UPDATE sme.tenants SET status='active' WHERE id=%s",
                        (self.tenant,))
        self.db.execute("UPDATE sme.sessions SET revoked_at=now() WHERE token_digest=%s",
                        (self.digest,))
        self.assertFalse(self.approve())
        self.db.execute("UPDATE sme.sessions SET revoked_at=NULL WHERE token_digest=%s",
                        (self.digest,))
        self.db.execute(
            "DELETE FROM sme.role_assignments WHERE tenant_id=%s AND id=%s",
            (self.tenant,self.role_id),
        )
        self.assertFalse(self.approve())

    def test_invalid_refs_rejected_and_no_write(self):
        for ref in ("../x","/absolute","https://evil","x"*129,"", "tenant/../x"):
            with self.subTest(ref=ref):
                self.assertFalse(self.approve(destination=ref))
                self.assertFalse(self.approve(secret=ref))
        self.assertFalse(self.approve(channel="sms"))
        self.assertIsNone(self.db.execute(
            "SELECT 1 FROM sme.asahi_delivery_destinations WHERE tenant_id=%s",
            (self.tenant,),
        ).fetchone())

    def test_wrong_tenant_denied(self):
        self.assertFalse(self.approve(tenant=uuid4()))
        self.assertFalse(self.revoke(tenant=uuid4()))

    def test_single_use_proof_and_payload_binding(self):
        proof = self.issue("approve", self.digest, self.tenant,
                           "email", "tenant/alerts", "tenant/secret")
        self.assertIsNotNone(proof)
        self.assertFalse(self.call("approve_asahi_delivery_stepup",
            self.digest,self.tenant,proof,"webhook","tenant/alerts","tenant/secret"))
        self.assertFalse(self.call("approve_asahi_delivery_stepup",
            self.digest,self.tenant,proof,"email","tenant/changed","tenant/secret"))
        self.assertFalse(self.call("approve_asahi_delivery_stepup",
            self.digest,uuid4(),proof,"email","tenant/alerts","tenant/secret"))
        self.assertFalse(self.call("approve_asahi_delivery_stepup",
            self.other_digest,self.tenant,proof,"email","tenant/alerts","tenant/secret"))
        self.assertTrue(self.call("approve_asahi_delivery_stepup",
            self.digest,self.tenant,proof,"email","tenant/alerts","tenant/secret"))
        self.assertFalse(self.call("approve_asahi_delivery_stepup",
            self.digest,self.tenant,proof,"email","tenant/alerts","tenant/secret"))

    def test_proof_action_expiry_and_revoked_session(self):
        proof=self.issue("revoke",self.digest,self.tenant)
        self.assertIsNotNone(proof)
        self.assertFalse(self.call("approve_asahi_delivery_stepup",
            self.digest,self.tenant,proof,"email","tenant/alerts","tenant/secret"))
        self.db.execute("UPDATE sme.asahi_stepup_proofs SET issued_at=now()-interval '120 seconds', expires_at=now()-interval '1 second' WHERE id=%s",
                        (proof,))
        self.assertFalse(self.call("revoke_asahi_delivery_stepup",
                                   self.digest,self.tenant,proof))
        self.assertIsNone(self.issue("approve",self.other_digest,self.tenant,
                        "email","tenant/alerts","tenant/secret"))
        self.db.execute("UPDATE sme.sessions SET revoked_at=now() WHERE token_digest=%s",
                        (self.digest,))
        self.assertIsNone(self.issue("approve",self.digest,self.tenant,
                        "email","tenant/alerts","tenant/secret"))

    def test_proof_issuer_and_legacy_approval_are_privilege_separated(self):
        for role in ("sme_app","sme_auth","sme_ingest","sme_dispatch","sme_approval"):
            with self.subTest(role=role),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                self.call("issue_asahi_stepup",self.digest,self.tenant,"approve",
                          "email","tenant/alerts","tenant/secret",60,role=role)
        for fn,args in (
            ("approve_asahi_delivery",(self.digest,self.tenant,"email","tenant/alerts","tenant/secret")),
            ("revoke_asahi_delivery",(self.digest,self.tenant)),
        ):
            with self.subTest(fn=fn),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                self.call(fn,*args,role="sme_approval")

    def test_invalid_proof_request_rejected(self):
        for lifetime in (0,14,121):
            self.assertIsNone(self.issue("approve",self.digest,self.tenant,
                "email","tenant/alerts","tenant/secret",lifetime=lifetime))
        self.assertIsNone(self.issue("revoke",self.digest,self.tenant,
                "email","tenant/alerts","tenant/secret"))
        self.assertIsNone(self.issue("approve",self.digest,self.tenant,
                "email","tenant/../unsafe","tenant/secret"))
        self.assertIsNone(self.issue("unknown",self.digest,self.tenant))

    def test_runtime_roles_no_direct_access(self):
        for role in ("sme_app","sme_auth","sme_ingest","sme_dispatch"):
            with self.subTest(role=role),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                self.approve(role=role)
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.db.transaction():
                self.db.execute("SET LOCAL ROLE sme_app")
                self.db.execute("UPDATE sme.asahi_delivery_destinations SET enabled=true")


if __name__=="__main__":
    unittest.main()
