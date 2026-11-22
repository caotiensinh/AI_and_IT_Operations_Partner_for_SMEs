"""Spec 022: full orchestrator using synthetic signed IdP, no external service."""
import hashlib
import json
import unittest
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit, parse_qs
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from sme_partner.asahi_stepup_oidc_flow import (
    AsahiStepupOIDCFlow, PostgresStepupStore, StepupAction, StepupRejected
)
from sme_partner.oidc import OIDCConfig
from sme_partner.oidc_flow import OIDCLoginSettings


class MemoryStepupStore:
    def __init__(self):
        self.pending={}
        self.proofs=[]
        self.tenant=uuid4()
        self.session=b"s"*32
        self.identity_value=("https://id.example","owner-subject")
        self.allowed=True

    def begin(self, *, state_digest, browser_digest, session_digest, action, verifier, nonce):
        if not self.allowed or session_digest!=self.session or action.tenant_id!=self.tenant:
            return False
        self.pending[state_digest]=(browser_digest,session_digest,action,verifier,nonce)
        return True

    def consume(self, *, state_digest, browser_digest, session_digest, action):
        value=self.pending.get(state_digest)
        if not value or value[:3]!=(browser_digest,session_digest,action):
            return None
        del self.pending[state_digest]
        return value[3:]

    def identity(self, session_digest, tenant):
        return self.identity_value if self.allowed and session_digest==self.session and tenant==self.tenant else None

    def issue(self, *, session_digest, action, lifetime):
        if not self.allowed or session_digest!=self.session or action.tenant_id!=self.tenant:
            return None
        proof=uuid4()
        self.proofs.append((proof,action,lifetime))
        return proof


class StepupOIDCOrchestratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        cls.other_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        jwk=json.loads(RSAAlgorithm.to_jwk(cls.key.public_key()))
        jwk.update({"kid":"trusted","alg":"RS256","use":"sig"})
        cls.config=OIDCConfig("https://id.example","sme-web",{"keys":[jwk]})

    def setUp(self):
        self.db=MemoryStepupStore()
        self.action=StepupAction(self.db.tenant,"approve","email","tenant/alerts","tenant/secret")
        self.override={}
        self.signing_key=self.key
        self.last_exchange=None
        self.callback_nonce=None
        def exchange(code,verifier,redirect_uri,client_id):
            self.last_exchange=(code,verifier,redirect_uri,client_id)
            now=int(datetime.now(timezone.utc).timestamp())
            claims={"iss":"https://id.example","sub":"owner-subject","aud":"sme-web",
                    "iat":now,"exp":now+300,"auth_time":now-5,
                    "nonce":self.callback_nonce,"amr":["pwd","otp"]}
            claims.update(self.override)
            return jwt.encode(claims,self.signing_key,algorithm="RS256",
                              headers={"kid":"trusted"})
        self.flow=AsahiStepupOIDCFlow(
            OIDCLoginSettings("https://id.example/authorize",
                              "https://app.example/stepup/callback",self.config),
            self.db,exchange)

    def start(self):
        started=self.flow.start(session_digest=self.db.session,action=self.action)
        params=parse_qs(urlsplit(started.authorization_url).query)
        self.callback_nonce=params["nonce"][0]
        return started,params

    def complete(self, started, action=None, session=None, browser=None, state=None):
        return self.flow.complete(
            session_digest=self.db.session if session is None else session,
            action=self.action if action is None else action,
            state=started.state if state is None else state,
            browser_binding=started.browser_binding if browser is None else browser,
            code="valid-authentication-code")

    def test_full_synthetic_pkce_mfa_to_proof(self):
        started,params=self.start()
        self.assertEqual(params["prompt"],["login"])
        self.assertEqual(params["max_age"],["0"])
        self.assertEqual(params["code_challenge_method"],["S256"])
        self.assertEqual(params["scope"],["openid"])
        self.assertNotIn("code_verifier",params)
        proof=self.complete(started)
        self.assertEqual(self.db.proofs[0][0],proof)
        self.assertEqual(self.db.proofs[0][2],60)
        self.assertEqual(self.last_exchange[2:],
                         ("https://app.example/stepup/callback","sme-web"))
        import base64
        actual=base64.urlsafe_b64encode(hashlib.sha256(
            self.last_exchange[1].encode("ascii")).digest()).rstrip(b"=").decode()
        self.assertEqual(params["code_challenge"][0],actual)

    def test_correct_state_single_use(self):
        started,_=self.start()
        self.complete(started)
        with self.assertRaises(StepupRejected):
            self.complete(started)
        self.assertEqual(len(self.db.proofs),1)

    def test_wrong_browser_session_action_tenant_and_payload_not_consumed(self):
        started,_=self.start()
        for overrides in (
            {"browser":"x"*43},{"session":b"x"*32},
            {"action":StepupAction(uuid4(),"approve","email","tenant/alerts","tenant/secret")},
            {"action":StepupAction(self.db.tenant,"revoke")},
            {"action":StepupAction(self.db.tenant,"approve","email","tenant/different","tenant/secret")},
            {"state":"y"*43},
        ):
            with self.subTest(overrides=overrides),self.assertRaises(StepupRejected):
                self.complete(started,**overrides)
        self.assertIsNotNone(self.complete(started))

    def test_failures_consume_challenge_and_never_issue_proof(self):
        for override in ({"amr":["pwd"]},{"auth_time":int(datetime.now(timezone.utc).timestamp())-600},
                         {"sub":"wrong-subject"},{"nonce":"wrong-nonce"}):
            with self.subTest(override=override):
                self.override=override
                started,_=self.start()
                with self.assertRaises(StepupRejected):
                    self.complete(started)
                with self.assertRaises(StepupRejected):
                    self.complete(started)
        self.assertEqual(self.db.proofs,[])

    def test_wrong_signature_and_revoked_owner_fail_closed(self):
        started,_=self.start()
        self.signing_key=self.other_key
        with self.assertRaises(StepupRejected):
            self.complete(started)
        self.assertFalse(self.db.proofs)
        self.signing_key=self.key
        started,_=self.start()
        self.db.allowed=False
        with self.assertRaises(StepupRejected):
            self.complete(started)
        self.assertFalse(self.db.proofs)

    def test_invalid_request_and_configuration(self):
        with self.assertRaises(ValueError):
            StepupAction(self.db.tenant,"approve","webhook","../escaped","secret/ref")
        with self.assertRaises(ValueError):
            StepupAction(self.db.tenant,"revoke","email","a","b")
        with self.assertRaises(ValueError):
            StepupAction(self.db.tenant,"approve","sms","a","b")
        with self.assertRaises(ValueError):
            AsahiStepupOIDCFlow(self.flow.settings,self.db,self.flow.exchange_code,
                                proof_lifetime=0)
        self.db.allowed=False
        with self.assertRaises(StepupRejected):
            self.start()


if __name__=="__main__":
    unittest.main()
