"""HTTP browser adapter regression tests (no external IdP or live credentials)."""
from __future__ import annotations

import secrets
import unittest
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

from sme_partner.oidc_browser import BrowserLoginSettings, create_oidc_browser_app
from sme_partner.oidc_flow import LoginRejected, LoginStart


class SyntheticFlow:
    def __init__(self):
        self.calls = []
        self.used = set()
        self.expected_state = secrets.token_urlsafe(32)
        self.binding = secrets.token_urlsafe(32)
        self.authorization_url = (
            "https://id.example/authorize?response_type=code&state="
            + self.expected_state + "&code_challenge=synthetic"
        )
        self.settings = type("Settings", (), {"session_lifetime_seconds": 3600})()

    def start(self):
        return LoginStart(self.authorization_url, self.expected_state, self.binding)

    def complete(self, *, state, browser_binding, code):
        self.calls.append((state, browser_binding, code))
        if (state != self.expected_state or browser_binding != self.binding
                or code != "synthetic-code" or state in self.used):
            raise LoginRejected("login failed")
        self.used.add(state)
        return "synthetic-opaque-session-never-put-in-redirect"


class BrowserOIDCTests(unittest.TestCase):
    def setUp(self):
        self.flow = SyntheticFlow()
        self.client = TestClient(
            create_oidc_browser_app(
                self.flow, settings=BrowserLoginSettings("/workspace")
            ),
            base_url="https://pilot.example",
            follow_redirects=False,
        )

    def tearDown(self):
        self.client.close()

    def test_start_is_external_redirect_with_bound_secure_cookie(self):
        response = self.client.get("/auth/oidc/start")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], self.flow.authorization_url)
        cookie = response.headers["set-cookie"]
        for required in ("__Host-sme_oidc_binding=", "HttpOnly", "Secure",
                         "SameSite=lax", "Path=/", "Max-Age=300"):
            self.assertIn(required, cookie)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn("synthetic-opaque-session", response.text)

    def test_callback_mints_secure_session_cookie_without_url_leak(self):
        self.client.get("/auth/oidc/start")
        r = self.client.get("/auth/oidc/callback", params={
            "state": self.flow.expected_state, "code": "synthetic-code",
            "redirect_uri": "https://attacker.example/steal",
        })
        self.assertEqual(r.status_code, 303, r.text)
        self.assertEqual(r.headers["location"], "/workspace")
        self.assertNotIn("synthetic-opaque-session", r.headers["location"])
        self.assertNotIn("synthetic-code", r.headers["location"])
        for required in ("__Host-sme_session=", "HttpOnly", "Secure",
                         "SameSite=lax", "Path=/", "Max-Age=3600"):
            self.assertIn(required, r.headers["set-cookie"])
        self.assertEqual(
            self.flow.calls, [(self.flow.expected_state, self.flow.binding, "synthetic-code")]
        )
        self.assertEqual(r.headers["cache-control"], "no-store")

    def test_missing_cookie_or_replay_is_denied_and_binding_cleared(self):
        denial = self.client.get("/auth/oidc/callback", params={
            "state": self.flow.expected_state, "code": "synthetic-code"
        })
        self.assertEqual(denial.status_code, 401)
        self.assertEqual(self.flow.calls, [])
        self.client.get("/auth/oidc/start")
        allowed = self.client.get("/auth/oidc/callback", params={
            "state": self.flow.expected_state, "code": "synthetic-code",
        })
        self.assertEqual(allowed.status_code, 303)
        replay = self.client.get("/auth/oidc/callback", params={
            "state": self.flow.expected_state, "code": "synthetic-code"
        })
        self.assertEqual(replay.status_code, 401)
        self.assertIn("Max-Age=0", replay.headers["set-cookie"])
        self.assertNotIn("synthetic-opaque-session", replay.text)

    def test_provider_error_never_exchanges_or_issues_session(self):
        self.client.get("/auth/oidc/start")
        r = self.client.get("/auth/oidc/callback", params={
            "error": "access_denied", "state": self.flow.expected_state,
            "code": "synthetic-code",
        })
        self.assertEqual(r.status_code, 401)
        self.assertEqual(self.flow.calls, [])
        self.assertNotIn("__Host-sme_session=", r.headers["set-cookie"])

    def test_wrong_browser_binding_and_missing_parameters_denied(self):
        self.client.get("/auth/oidc/start")
        self.client.cookies.set("__Host-sme_oidc_binding", secrets.token_urlsafe(32),
                                domain="pilot.example", path="/")
        wrong = self.client.get("/auth/oidc/callback", params={
            "state": self.flow.expected_state, "code": "synthetic-code",
        })
        self.assertEqual(wrong.status_code, 401)
        for q in ({"state": self.flow.expected_state}, {"code": "synthetic-code"}):
            self.assertEqual(self.client.get("/auth/oidc/callback", params=q).status_code, 401)

    def test_post_login_redirect_must_be_fixed_local_path(self):
        for unsafe in ("https://evil.example/", "//evil.example", "/foo?next=https://evil",
                       "/foo#fragment", "/\\evil", ""):
            with self.subTest(unsafe=unsafe):
                with self.assertRaises(ValueError):
                    BrowserLoginSettings(unsafe)
        self.assertEqual(BrowserLoginSettings("/workspace").post_login_path, "/workspace")

    def test_token_exchange_internal_failure_never_disclosed(self):
        self.client.get("/auth/oidc/start")
        def failing(**kwargs):
            raise RuntimeError("sensitive infrastructure diagnostic")
        self.flow.complete = failing
        r = self.client.get("/auth/oidc/callback", params={
            "state": self.flow.expected_state, "code": "synthetic-code",
        })
        self.assertEqual(r.status_code, 401)
        self.assertNotIn("sensitive", r.text)
        self.assertNotIn("__Host-sme_session=", r.headers["set-cookie"])


if __name__ == "__main__":
    unittest.main()
