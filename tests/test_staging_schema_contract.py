"""Regression contract for the canonical staging migration namespace.

The main branch owns migrations 0001-0019 and Discovery/OIDC additions use
0020-0026. Both tenant selector APIs coexist with distinct return signatures.
This test is safe against a disposable PostgreSQL database only.
"""
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"


class StagingSchemaContractTests(unittest.TestCase):
    def test_unique_ordered_migrations_0001_through_0026(self):
        names = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
        self.assertEqual(len(names), 28)
        numbers = [int(name.split("_", 1)[0]) for name in names]
        self.assertEqual(numbers, list(range(1, 22)) + list(range(100, 107)))
        self.assertIn("0008_discovery_read_model.sql", names)
        self.assertIn("0100_discovery_case_write.sql", names)
        self.assertIn("0106_cookie_bff_tenants.sql", names)

    def test_main_and_cookie_selectors_have_separate_contracts(self):
        main = (MIGRATIONS / "0006_tenant_selector.sql").read_text()
        cookie = (MIGRATIONS / "0106_cookie_bff_tenants.sql").read_text()
        self.assertIn("FUNCTION sme.list_session_tenants(", main)
        self.assertIn("display_name text", main)
        self.assertIn("FUNCTION sme.list_browser_session_tenants(", cookie)
        self.assertIn("tenant_label text", cookie)
        self.assertIn("LIMIT 101", cookie)
        self.assertIn("TO sme_app", cookie)
        self.assertNotIn("CREATE OR REPLACE FUNCTION sme.list_session_tenants(", cookie)

    @unittest.skipUnless(os.getenv("SME_TEST_DATABASE_DSN"), "Requires disposable PostgreSQL")
    def test_two_distinct_live_postgresql_functions_and_denied_raw_sessions(self):
        import psycopg
        dsn = os.environ["SME_TEST_DATABASE_DSN"]
        with psycopg.connect(dsn, autocommit=True) as connection:
            # All migrations must be reentrant in a disposable test DB, and
            # running them again must not change an existing function signature.
            for path in sorted(MIGRATIONS.glob("*.sql")):
                connection.execute(path.read_text())
            result = connection.execute(
                "SELECT proname, pg_get_function_result(p.oid) "
                "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                "WHERE n.nspname='sme' AND p.proname = ANY(%s) "
                "ORDER BY proname",
                (["list_session_tenants", "list_browser_session_tenants"],),
            ).fetchall()
            self.assertEqual(len(result), 2)
            columns = dict(result)
            self.assertIn("display_name", columns["list_session_tenants"])
            self.assertIn("tenant_label", columns["list_browser_session_tenants"])
            with connection.transaction():
                connection.execute("SET LOCAL ROLE sme_app")
                self.assertFalse(connection.execute(
                    "SELECT has_table_privilege(current_user,'sme.sessions','SELECT')"
                ).fetchone()[0])
                self.assertTrue(connection.execute(
                    "SELECT has_function_privilege(current_user,"
                    "'sme.list_browser_session_tenants(bytea)','EXECUTE')"
                ).fetchone()[0])


if __name__ == "__main__":
    unittest.main()
