"""PostgreSQL acceptance for a tenant-authorized lease-bound routing lookup."""
import os
import unittest
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
try:
    import psycopg
except ImportError:
    psycopg = None

DSN = os.getenv("SME_TEST_DATABASE_DSN")
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(DSN and psycopg, "requires disposable PostgreSQL")
class DeliveryStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = psycopg.connect(DSN, autocommit=True)
        for path in sorted((ROOT / "migrations").glob("*.sql")):
            cls.db.execute(path.read_text())

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def setUp(self):
        self.tenant, self.identity, self.site, self.device, self.worker = [uuid4() for _ in range(5)]
        self.db.execute(
            "INSERT INTO sme.tenants(id,slug,display_name) VALUES (%s,%s,'Delivery')",
            (self.tenant, "delivery-" + self.tenant.hex[:12]),
        )
        self.db.execute(
            "INSERT INTO sme.identities(id,issuer,subject) VALUES (%s,'test-idp',%s)",
            (self.identity, self.identity.hex),
        )
        self.db.execute(
            "INSERT INTO sme.memberships(tenant_id,identity_id) VALUES (%s,%s)",
            (self.tenant, self.identity),
        )
        self.db.execute(
            "INSERT INTO sme.sites(tenant_id,id,label) VALUES (%s,%s,'Lab')",
            (self.tenant, self.site),
        )
        self.db.execute(
            "INSERT INTO sme.assets(tenant_id,id,site_id,name) VALUES (%s,%s,%s,'Server')",
            (self.tenant, self.device, self.site),
        )
        self.event = self.db.execute(
            "INSERT INTO sme.asahi_alert_outbox(tenant_id,site_id,device_id,metric,transition,sampled_at,metric_value)"
            " VALUES (%s,%s,%s,'cpu','triggered',%s,95) RETURNING id",
            (self.tenant, self.site, self.device, datetime.now(timezone.utc)),
        ).fetchone()[0]

    def configure(self, *, enabled=False, revoked=False):
        self.db.execute(
            "INSERT INTO sme.asahi_delivery_destinations"
            "(tenant_id,channel,destination_ref,secret_ref,enabled,approved_by,revoked_at)"
            " VALUES (%s,'email','tenant/mail/ops','tenant/mail/token',%s,%s,"
            " CASE WHEN %s THEN now() ELSE NULL END)",
            (self.tenant, enabled, self.identity, revoked),
        )

    def claim(self):
        with psycopg.connect(DSN) as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE sme_dispatch")
                return conn.execute(
                    "SELECT * FROM sme.claim_asahi_alert(%s,%s,30)",
                    (self.tenant, self.worker),
                ).fetchall()

    def resolve(self, *, role="sme_dispatch", event=None, owner=None):
        with psycopg.connect(DSN) as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE " + role)
                return conn.execute(
                    "SELECT * FROM sme.resolve_asahi_delivery(%s,%s)",
                    (self.event if event is None else event,
                     self.worker if owner is None else owner),
                ).fetchall()

    def test_requires_explicit_enabled_configuration_and_claim(self):
        self.configure(enabled=True)
        self.assertEqual(self.resolve(), [])
        self.assertEqual(len(self.claim()), 1)
        row = self.resolve()[0]
        self.assertEqual(row, (self.tenant, "email", "tenant/mail/ops",
                               "tenant/mail/token", str(self.event)))
        self.assertEqual(self.resolve(), [row])

    def test_disabled_revoked_and_missing_policy_are_denied(self):
        self.assertEqual(len(self.claim()), 1)
        self.assertEqual(self.resolve(), [])
        self.configure(enabled=False)
        self.assertEqual(self.resolve(), [])
        self.db.execute(
            "UPDATE sme.asahi_delivery_destinations SET enabled=true WHERE tenant_id=%s",
            (self.tenant,),
        )
        self.assertEqual(len(self.resolve()), 1)
        self.db.execute(
            "UPDATE sme.asahi_delivery_destinations SET enabled=false,revoked_at=now() "
            "WHERE tenant_id=%s", (self.tenant,),
        )
        self.assertEqual(self.resolve(), [])

    def test_owner_lease_and_tenant_status_enforced(self):
        self.configure(enabled=True)
        self.claim()
        self.assertEqual(self.resolve(owner=uuid4()), [])
        self.assertEqual(self.resolve(event=self.event + 1000000000), [])
        self.db.execute(
            "UPDATE sme.asahi_alert_outbox SET delivery_lease_until=now()-interval '1 second' "
            "WHERE id=%s", (self.event,),
        )
        self.assertEqual(self.resolve(), [])
        self.db.execute(
            "UPDATE sme.asahi_alert_outbox SET delivery_lease_until=now()+interval '10 seconds' "
            "WHERE id=%s", (self.event,),
        )
        self.db.execute("UPDATE sme.tenants SET status='suspended' WHERE id=%s", (self.tenant,))
        self.assertEqual(self.resolve(), [])

    def test_app_auth_ingest_denied(self):
        self.configure(enabled=True)
        self.claim()
        for role in ("sme_app", "sme_auth", "sme_ingest"):
            with self.subTest(role=role), self.assertRaises(psycopg.errors.InsufficientPrivilege):
                self.resolve(role=role)

    def test_direct_table_access_denied(self):
        for role in ("sme_app", "sme_auth", "sme_ingest", "sme_dispatch"):
            with self.subTest(role=role), self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with self.db.transaction():
                    self.db.execute("SET LOCAL ROLE " + role)
                    self.db.execute("SELECT * FROM sme.asahi_delivery_destinations")

    def test_audit_insert_update_revoke(self):
        self.configure(enabled=False)
        self.db.execute(
            "UPDATE sme.asahi_delivery_destinations SET enabled=true WHERE tenant_id=%s",
            (self.tenant,),
        )
        self.db.execute(
            "UPDATE sme.asahi_delivery_destinations SET enabled=false,revoked_at=now() "
            "WHERE tenant_id=%s", (self.tenant,),
        )
        rows = self.db.execute(
            "SELECT operation,previous_enabled,current_enabled FROM sme.asahi_delivery_policy_audit "
            "WHERE tenant_id=%s ORDER BY id", (self.tenant,),
        ).fetchall()
        self.assertEqual(rows, [("created", None, False), ("updated", False, True),
                                ("revoked", True, False)])

    def test_invalid_reference_and_revoked_enabled_rejected(self):
        for destination in ("https://evil", "/etc/passwd", "../escape", ""):
            with self.subTest(destination=destination), self.assertRaises(psycopg.errors.CheckViolation):
                self.db.execute(
                    "INSERT INTO sme.asahi_delivery_destinations"
                    "(tenant_id,channel,destination_ref,secret_ref,approved_by) "
                    "VALUES (%s,'email',%s,'tenant/mail/token',%s)",
                    (self.tenant, destination, self.identity),
                )
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.configure(enabled=True, revoked=True)

    def test_delete_forbidden_and_tenant_move_forbidden(self):
        self.configure()
        with self.assertRaises(psycopg.errors.RaiseException):
            self.db.execute("DELETE FROM sme.asahi_delivery_destinations WHERE tenant_id=%s",
                            (self.tenant,))
        with self.assertRaises(psycopg.errors.RaiseException):
            self.db.execute(
                "UPDATE sme.asahi_delivery_destinations SET tenant_id=%s WHERE tenant_id=%s",
                (uuid4(), self.tenant),
            )


if __name__ == "__main__":
    unittest.main()
