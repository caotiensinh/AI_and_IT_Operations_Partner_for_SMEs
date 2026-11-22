"""Real PostgreSQL read-only preflight with disposable, independent LOGIN roles."""
import os
import secrets
import unittest
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from sme_partner.oidc_preflight import run_preflight
from test_discovery_runtime import HTTP,env

DSN=os.getenv("SME_TEST_DATABASE_DSN")
ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(DSN,"Requires disposable PostgreSQL")
class PreflightDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.owner=psycopg.connect(DSN,autocommit=True)
        for n in (1, 2, 3, 4, 5, 6, 7, 8, 9, 20, 21, 22, 23, 24, 25, 26):
            files=list((ROOT/"migrations").glob(f"{n:04d}_*.sql"))
            if len(files)!=1:
                raise RuntimeError("Expected one migration")
            cls.owner.execute(files[0].read_text())
        cls.app_name="pf_app_"+uuid4().hex[:16]
        cls.auth_name="pf_auth_"+uuid4().hex[:16]
        cls.app_password=secrets.token_urlsafe(30)
        cls.auth_password=secrets.token_urlsafe(30)
        for role,password,member in (
            (cls.app_name,cls.app_password,"sme_app"),
            (cls.auth_name,cls.auth_password,"sme_auth"),
        ):
            cls.owner.execute(
                sql.SQL("CREATE ROLE {} LOGIN NOINHERIT PASSWORD {}").format(
                    sql.Identifier(role),sql.Literal(password)))
            cls.owner.execute(
                sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(member),sql.Identifier(role)))
        cls.values=env()
        cls.values["SME_OIDC_REQUIRE_MFA"]="true"
        cls.values["SME_APP_DATABASE_DSN"]=make_conninfo(
            DSN,user=cls.app_name,password=cls.app_password)
        cls.values["SME_AUTH_DATABASE_DSN"]=make_conninfo(
            DSN,user=cls.auth_name,password=cls.auth_password)

    @classmethod
    def tearDownClass(cls):
        try:
            for role in (cls.app_name,cls.auth_name):
                cls.owner.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
        finally:
            cls.owner.close()

    def test_real_postgres_app_and_auth_login_boundaries(self):
        report=run_preflight(self.values,provider_http=HTTP())
        self.assertTrue(report.ready,report.public_dict())
        self.assertEqual(len(report.checks),22)
        self.assertTrue(all(x.passed for x in report.checks))
        output=str(report.public_dict())
        self.assertNotIn(self.app_password,output)
        self.assertNotIn(self.auth_password,output)

    def test_cross_assigned_auth_privileges_fail_closed(self):
        # A misconfiguration granting sme_auth to app login must block rollout.
        self.owner.execute(sql.SQL("GRANT sme_auth TO {}").format(
            sql.Identifier(self.app_name)))
        try:
            report=run_preflight(self.values,provider_http=HTTP())
            self.assertFalse(report.ready)
            failed={c.name for c in report.checks if not c.passed}
            self.assertIn("db.sme_app.identity",failed)
        finally:
            self.owner.execute(sql.SQL("REVOKE sme_auth FROM {}").format(
                sql.Identifier(self.app_name)))

    def test_superuser_identity_fails_closed(self):
        # Synthetic privileged owner is never an acceptable runtime login.
        values=dict(self.values)
        values["SME_APP_DATABASE_DSN"]=DSN
        result=run_preflight(values,provider_http=HTTP())
        self.assertFalse(result.ready)
        self.assertIn("db.sme_app.identity",
            {c.name for c in result.checks if not c.passed})


if __name__=="__main__":
    unittest.main()
