"""Spec 023: HTTPS cookie-only browser BFF negative and success regressions."""
import unittest
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sme_partner.asahi_stepup_bff import install_asahi_stepup_bff
from sme_partner.asahi_stepup_oidc_flow import StepupAction, StepupStart, StepupRejected
from sme_partner.browser_gateway import SESSION_COOKIE, _session_csrf
from sme_partner.oidc_flow import _digest


class MemoryChallenge:
    def __init__(self):
        self.pending=None
        self.used=False
    def lookup(self, *, state_digest,browser_digest,session_digest):
        if (self.pending is None or self.used or
            (state_digest,browser_digest,session_digest)!=self.pending[:3]):
            return None
        return self.pending[3]


class FakeStepupFlow:
    def __init__(self):
        self.store=MemoryChallenge()
        self.tenant=uuid4()
        self.completed=0
    def start(self, *, session_digest,action):
        if action.tenant_id!=self.tenant:
            raise StepupRejected("wrong tenant")
        state="s"*43
        browser="b"*43
        self.store.pending=(_digest(state),_digest(browser),session_digest,action)
        self.store.used=False
        return StepupStart("https://id.example/authorize?state="+state,state,browser)
    def complete(self, *, session_digest,action,state,browser_binding,code):
        row=self.store.lookup(state_digest=_digest(state),
                              browser_digest=_digest(browser_binding),
                              session_digest=session_digest)
        if row!=action or code!="valid-auth-code-12345":
            raise StepupRejected("invalid challenge")
        self.store.used=True
        self.completed+=1
        return uuid4()


class StepupBffTests(unittest.TestCase):
    def setUp(self):
        self.flow=FakeStepupFlow()
        self.active=True
        self.applied=[]
        self.key=b"k"*32
        self.app=FastAPI()
        install_asahi_stepup_bff(
            self.app,self.flow,public_origin="https://app.example",
            csrf_key=self.key,session_active=lambda token:self.active and token=="t"*43,
            apply_proof=lambda digest,action,proof:
                self.applied.append((digest,action,proof)) or True,
            enabled=True,
        )
        self.client=TestClient(self.app,base_url="https://app.example",
                               follow_redirects=False)
        self.client.cookies.set(SESSION_COOKIE,"t"*43,domain="app.example",path="/")
        self.endpoint=f"/v1/tenants/{self.flow.tenant}/itops/asahi/stepup/start"
        self.body={"action":"approve","channel":"email",
                   "destination_ref":"tenant/alerts","secret_ref":"tenant/secret"}
    def request(self, headers=None, body=None):
        if headers is None:
            headers={"Origin":"https://app.example",
                     "X-CSRF-Token":_session_csrf("t"*43,self.key)}
        return self.client.post(self.endpoint,headers=headers,
                                json=self.body if body is None else body)
    def callback(self, **overrides):
        query={"state":"s"*43,"code":"valid-auth-code-12345"}
        query.update(overrides)
        return self.client.get("/auth/asahi/stepup/callback",params=query)

    def test_https_start_to_callback_applies_server_bound_action(self):
        r=self.request()
        self.assertEqual(r.status_code,303,r.text)
        self.assertEqual(r.headers["location"],
                         "https://id.example/authorize?state="+"s"*43)
        self.assertIn("Secure",r.headers["set-cookie"])
        self.assertIn("HttpOnly",r.headers["set-cookie"])
        self.assertIn("SameSite=lax",r.headers["set-cookie"])
        self.assertIn("no-store",r.headers["cache-control"])
        result=self.callback()
        self.assertEqual(result.status_code,303,result.text)
        self.assertEqual(result.headers["location"],"https://app.example/app")
        self.assertEqual(len(self.applied),1)
        self.assertEqual(self.applied[0][1].destination_ref,"tenant/alerts")
        self.assertEqual(self.callback().status_code,403)
        self.assertEqual(len(self.applied),1)

    def test_bad_origin_csrf_and_cookies_rejected(self):
        for headers in (
            {"X-CSRF-Token":_session_csrf("t"*43,self.key)},
            {"Origin":"https://evil.example",
             "X-CSRF-Token":_session_csrf("t"*43,self.key)},
            {"Origin":"https://app.example","X-CSRF-Token":"wrong"},
        ):
            with self.subTest(headers=headers):
                self.assertEqual(self.request(headers=headers).status_code,403)
                self.assertEqual(self.applied,[])
        self.client.cookies.clear()
        self.assertEqual(self.request().status_code,403)

    def test_invalid_target_and_unknown_payload_denied(self):
        for body in (
            {"action":"approve","channel":"email",
             "destination_ref":"../evil","secret_ref":"tenant/secret"},
            {"action":"approve","channel":"sms",
             "destination_ref":"tenant/alerts","secret_ref":"tenant/secret"},
            {"action":"revoke","channel":"email"},
        ):
            with self.subTest(body=body):
                self.assertEqual(self.request(body=body).status_code,403)
        self.assertEqual(self.request(body={**self.body,"owner":True}).status_code,422)

    def test_callback_rejects_forgery_and_not_uses_query_target(self):
        self.request()
        self.assertEqual(self.callback(state="x"*43).status_code,403)
        self.assertEqual(self.callback(code="invalid-code-1234567").status_code,403)
        # The query target is ignored; only server-persisted action gets applied.
        self.assertEqual(self.callback(tenant="attacker",destination_ref="other").status_code,303)
        self.assertEqual(self.applied[0][1].destination_ref,"tenant/alerts")

    def test_missing_browser_and_revoked_session_denied(self):
        self.request()
        self.client.cookies.delete("__Host-sme_stepup_bind",domain="app.example",path="/")
        self.assertEqual(self.callback().status_code,403)
        self.request()
        self.active=False
        self.assertEqual(self.callback().status_code,403)
        self.assertEqual(self.applied,[])

    def test_disabled_by_default_and_invalid_origin_config(self):
        app=FastAPI()
        install_asahi_stepup_bff(app,self.flow,public_origin="https://app.example",
            csrf_key=self.key,session_active=lambda token:True,
            apply_proof=lambda digest,action,proof:True)
        client=TestClient(app,base_url="https://app.example")
        self.assertEqual(client.post(self.endpoint,json=self.body).status_code,503)
        self.assertEqual(client.get("/auth/asahi/stepup/callback").status_code,503)
        for origin in ("http://app.example","https://evil@app.example",
                       "https://app.example/unsafe"):
            with self.subTest(origin=origin),self.assertRaises(ValueError):
                install_asahi_stepup_bff(FastAPI(),self.flow,
                  public_origin=origin,csrf_key=self.key,
                  session_active=lambda token:True,
                  apply_proof=lambda digest,action,proof:True,enabled=True)
