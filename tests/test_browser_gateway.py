import hashlib
import hmac
import unittest
from urllib.parse import parse_qs,urlsplit
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sme_partner.browser_gateway import install_browser_gateway
from sme_partner.oidc_flow import LoginStart, LoginRejected, OIDCLoginSettings
from sme_partner.oidc import OIDCConfig
from sme_partner.oidc_exchange import OIDCTokenExchange
import httpx


class FakeFlow:
    settings = type("Settings",(),{"session_lifetime_seconds":3600})()
    def __init__(self):self.used=set();self.issued=0
    def start(self):
        return LoginStart("https://id.example/authorize?state=fake","a"*43,"b"*43)
    def complete(self, *, state,browser_binding,code):
        if state!="a"*43 or browser_binding!="b"*43 or code!="approved-code-value":
            raise LoginRejected("login failed")
        if state in self.used:raise LoginRejected("replay")
        self.used.add(state);self.issued+=1
        return "c"*43


class BrowserGatewayTests(unittest.TestCase):
    def setUp(self):
        self.flow=FakeFlow()
        self.revoked=[]
        self.active_tokens={'c'*43}
        self.app=FastAPI()
        install_browser_gateway(self.app,self.flow,public_origin="https://app.example",
                                csrf_key=b"k"*32,revoke_session=self.revoked.append,
                                session_active=lambda token: token in self.active_tokens and token not in self.revoked)
        self.client=TestClient(self.app,base_url="https://app.example",follow_redirects=False)
    def test_start_sets_secure_binding_cookie(self):
        r=self.client.get("/auth/start")
        self.assertEqual(r.status_code,302)
        self.assertEqual(r.headers["location"],"https://id.example/authorize?state=fake")
        self.assertIn("Secure",r.headers["set-cookie"])
        self.assertIn("HttpOnly",r.headers["set-cookie"])
        self.assertIn("SameSite=lax",r.headers["set-cookie"])
        self.assertIn("no-store",r.headers["cache-control"])
    def test_callback_sets_secure_session_and_clears_binding(self):
        self.client.get("/auth/start")
        r=self.client.get("/auth/callback",params={"state":"a"*43,"code":"approved-code-value"})
        self.assertEqual(r.status_code,303)
        self.assertEqual(r.headers["location"],"https://app.example/app")
        self.assertIn("__Host-sme_session",r.headers["set-cookie"])
        self.assertIn("Secure",r.headers["set-cookie"])
        self.assertIn("HttpOnly",r.headers["set-cookie"])
    def test_missing_cookie_denied(self):
        r=self.client.get("/auth/callback",params={"state":"a"*43,"code":"approved-code-value"})
        self.assertEqual(r.status_code,401)
    def test_invalid_state_denied(self):
        self.client.get("/auth/start")
        r=self.client.get("/auth/callback",params={"state":"b"*43,"code":"approved-code-value"})
        self.assertEqual(r.status_code,401)
    def test_csrf_and_logout(self):
        self.client.get("/auth/start")
        self.client.get("/auth/callback",params={"state":"a"*43,"code":"approved-code-value"})
        csrf=self.client.get("/auth/csrf")
        self.assertEqual(csrf.status_code,200)
        r=self.client.post("/auth/logout",headers={
            "Origin":"https://app.example",
            "X-CSRF-Token":csrf.json()["csrf_token"]})
        self.assertEqual(r.status_code,204)
        self.assertEqual(self.revoked,["c"*43])
    def test_revoked_session_cannot_get_csrf(self):
        self.client.get("/auth/start")
        self.client.get("/auth/callback",params={"state":"a"*43,"code":"approved-code-value"})
        self.active_tokens.clear()
        self.assertEqual(self.client.get("/auth/csrf").status_code,401)

    def test_inactive_session_cannot_logout(self):
        self.client.get("/auth/start")
        self.client.get("/auth/callback",params={"state":"a"*43,"code":"approved-code-value"})
        csrf=self.client.get("/auth/csrf").json()["csrf_token"]
        self.active_tokens.clear()
        response=self.client.post("/auth/logout",
            headers={"Origin":"https://app.example","X-CSRF-Token":csrf})
        self.assertEqual(response.status_code,403)
        self.assertEqual(self.revoked,[])

    def test_logout_rejects_forged_csrf(self):
        self.client.get("/auth/start")
        self.client.get("/auth/callback",params={"state":"a"*43,"code":"approved-code-value"})
        r=self.client.post("/auth/logout",headers={
            "Origin":"https://app.example","X-CSRF-Token":"bad"})
        self.assertEqual(r.status_code,403)
        self.assertEqual(self.revoked,[])
    def test_logout_rejects_missing_origin(self):
        self.client.get("/auth/start")
        self.client.get("/auth/callback",params={"state":"a"*43,"code":"approved-code-value"})
        csrf=self.client.get("/auth/csrf").json()["csrf_token"]
        r=self.client.post("/auth/logout",headers={"X-CSRF-Token":csrf})
        self.assertEqual(r.status_code,403)
    def test_rejects_insecure_origin_or_short_key(self):
        with self.assertRaises(ValueError):
            install_browser_gateway(FastAPI(),self.flow,public_origin="http://localhost",
                                    csrf_key=b"k"*32,revoke_session=self.revoked.append,
                                    session_active=lambda token: True)
        with self.assertRaises(ValueError):
            install_browser_gateway(FastAPI(),self.flow,public_origin="https://app.example",
                                    csrf_key=b"short",revoke_session=self.revoked.append,
                                    session_active=lambda token: True)


class ExchangeTests(unittest.TestCase):
    def test_pinned_endpoint_and_payload(self):
        def responder(req):
            self.assertEqual(req.url.host,"id.example")
            body=req.content.decode()
            for marker in ("grant_type=authorization_code","code_verifier=verifier","client_id=sme-web"):
                self.assertIn(marker,body)
            return httpx.Response(200,json={"id_token":"abc.def.ghi"})
        with httpx.Client(transport=httpx.MockTransport(responder)) as client:
            ex=OIDCTokenExchange("https://id.example/token",client=client)
            self.assertEqual(ex("code","verifier","https://app.example/auth/callback","sme-web"),"abc.def.ghi")
    def test_non_200_and_redirect_denied(self):
        from sme_partner.oidc import AuthenticationDenied
        for status in (302,400,500):
            with httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(status))) as client:
                with self.assertRaises(AuthenticationDenied):
                    OIDCTokenExchange("https://id.example/token",client=client)("c","v","https://app.example/cb","client")
    def test_untrusted_endpoint_denied(self):
        for url in ("http://id.example/token","https://evil@example.com/token","https://id.example/token#frag"):
            with self.assertRaises(ValueError):OIDCTokenExchange(url)


if __name__=="__main__":unittest.main()
