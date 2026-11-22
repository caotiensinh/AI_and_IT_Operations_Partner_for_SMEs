"""Deployment readiness acceptance: positive, negative, boundary, redaction tests."""
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from sme_partner.oidc_preflight import run_preflight,main,Check,Report
from sme_partner.oidc_provider import ProviderUnavailable
from test_discovery_runtime import env,HTTP


def ready_env():
    values=env()
    values["SME_OIDC_REQUIRE_MFA"]="true"
    return values


class PreflightTests(unittest.TestCase):
    def test_empty_config_fails_without_secret_or_network(self):
        report=run_preflight({},check_network=False,check_database=False)
        self.assertFalse(report.ready)
        self.assertEqual(report.checks[0].name,"config.required")
        self.assertEqual(len(report.checks),1)

    def test_offline_valid_config_passes_policy_and_local_checks_only(self):
        report=run_preflight(ready_env(),check_network=False,check_database=False)
        self.assertTrue(report.ready,report.public_dict())
        self.assertEqual(
            [x.name for x in report.checks],
            ["config.required","config.database_split","config.csrf",
             "config.origin","config.callback","config.mfa_policy","provider.pinned"])
        self.assertNotIn(ready_env()["SME_OIDC_CLIENT_SECRET"],str(report.public_dict()))

    def test_all_check_ids_stable_with_pinned_provider_network(self):
        provider=HTTP()
        report=run_preflight(ready_env(),provider_http=provider,check_database=False)
        self.assertTrue(report.ready,report.public_dict())
        self.assertEqual(provider.calls,[
            "https://id.example/.well-known/openid-configuration",
            "https://keys.example/jwks"])
        self.assertIn("provider.jwks",[c.name for c in report.checks])

    def test_mfa_and_callback_and_csrf_fail_independently(self):
        config=ready_env()
        config["SME_OIDC_REQUIRE_MFA"]="false"
        config["SME_OIDC_REDIRECT_URI"]="https://other.example/auth/oidc/callback"
        config["SME_CSRF_SECRET_HEX"]="wrong"
        report=run_preflight(config,check_network=False,check_database=False)
        failed={c.name for c in report.checks if not c.passed}
        self.assertEqual(failed,{"config.mfa_policy","config.callback","config.csrf"})
        self.assertFalse(report.ready)

    def test_network_fails_closed_without_echoing_credentials(self):
        config=ready_env()
        http=HTTP()
        http.fail=True
        report=run_preflight(config,provider_http=http,check_database=False)
        self.assertFalse(report.ready)
        failure={c.name for c in report.checks if not c.passed}
        self.assertEqual(failure,{"provider.discovery","provider.jwks"})
        out=json.dumps(report.public_dict())
        self.assertNotIn(config["SME_OIDC_CLIENT_SECRET"],out)
        self.assertNotIn(config["SME_APP_DATABASE_DSN"],out)
        self.assertNotIn(config["SME_CSRF_SECRET_HEX"],out)

    def test_db_connection_failure_not_exposed(self):
        def failing(_):
            raise OSError("postgresql://user:private-secret@db.example")
        report=run_preflight(ready_env(),provider_http=HTTP(),db_connect=failing)
        self.assertFalse(report.ready)
        self.assertEqual(
            {c.name for c in report.checks if not c.passed},
            {"db.sme_app.connection","db.sme_auth.connection"})
        self.assertNotIn("private-secret",str(report.public_dict()))

    def test_main_returns_nonzero_on_missing_credentials_redacted(self):
        output=io.StringIO()
        with patch.dict("os.environ",{},clear=True),redirect_stdout(output):
            code=main()
        self.assertEqual(code,1)
        payload=json.loads(output.getvalue())
        self.assertFalse(payload["ready"])
        self.assertNotIn("SME_OIDC_CLIENT_SECRET",str(payload))

    def test_report_ready_requires_all_checks(self):
        self.assertFalse(Report(()).ready)
        self.assertTrue(Report((Check("one",True,"ok"),)).ready)
        self.assertFalse(Report((Check("one",True,"ok"),Check("two",False,"fail"))).ready)


if __name__=="__main__":
    unittest.main()
