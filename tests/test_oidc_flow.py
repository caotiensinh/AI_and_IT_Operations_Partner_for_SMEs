import hashlib
import unittest
from urllib.parse import parse_qs,urlsplit
from datetime import datetime, timedelta, timezone
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
import json

from sme_partner.oidc import OIDCConfig
from sme_partner.oidc_flow import OIDCLoginFlow, OIDCLoginSettings, LoginRejected

class MemoryStore:
    def __init__(self):self.pending={};self.sessions={};self.allowed=True
    def begin(self,s,b,v,n): self.pending[s]=(b,v,n)
    def consume(self,s,b):
        p=self.pending.get(s)
        if not p or p[0]!=b:return None
        del self.pending[s]
        return p[1:]
    def issue(self,issuer,sub,digest,ttl):
        if not self.allowed or sub!='demo-user':return False
        self.sessions[digest]=ttl;return True

class FlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        jwk=json.loads(RSAAlgorithm.to_jwk(cls.key.public_key()))
        jwk.update({'kid':'k1','alg':'RS256','use':'sig'})
        cls.config=OIDCConfig('https://id.example','sme-web',{'keys':[jwk]},require_mfa=True)
        cls.settings=OIDCLoginSettings('https://id.example/authorize','https://app.example/auth/callback',cls.config)
    def setUp(self):
        self.store=MemoryStore()
        self.claim_override={}
        self.last_exchange=None
        def exchange(code,verifier,redirect,client):
            self.last_exchange=(code,verifier,redirect,client)
            claims={'iss':'https://id.example','aud':'sme-web','sub':'demo-user',
                    'iat':int(datetime.now(timezone.utc).timestamp()),
                    'exp':int((datetime.now(timezone.utc)+timedelta(minutes=5)).timestamp()),
                    'amr':['pwd','otp'],'nonce':self.nonce}
            claims.update(self.claim_override)
            return jwt.encode(claims,self.key,algorithm='RS256',headers={'kid':'k1'})
        self.flow=OIDCLoginFlow(self.settings,self.store,exchange)
    def start(self):
        start=self.flow.start()
        params=parse_qs(urlsplit(start.authorization_url).query)
        self.nonce=params['nonce'][0]
        return start,params
    def test_pkce_flow_and_session(self):
        begin,params=self.start()
        self.assertEqual(params['code_challenge_method'],['S256'])
        self.assertEqual(params['response_type'],['code'])
        self.assertEqual(params['redirect_uri'],['https://app.example/auth/callback'])
        self.assertNotIn('code_verifier',params)
        token=self.flow.complete(state=begin.state,browser_binding=begin.browser_binding,code='valid-authorization-code')
        self.assertEqual(len(token),43)
        self.assertEqual(len(self.store.sessions),1)
        self.assertEqual(self.last_exchange[2:4],('https://app.example/auth/callback','sme-web'))
        self.assertEqual(params['code_challenge'][0],__import__('base64').urlsafe_b64encode(
            hashlib.sha256(self.last_exchange[1].encode()).digest()).rstrip(b'=').decode())
    def test_replay_fails(self):
        begin,_=self.start()
        self.flow.complete(state=begin.state,browser_binding=begin.browser_binding,code='valid-code-value-1')
        with self.assertRaises(LoginRejected):
            self.flow.complete(state=begin.state,browser_binding=begin.browser_binding,code='valid-code-value-1')
    def test_wrong_browser_cookie_denied_without_consuming_state(self):
        begin,_=self.start()
        with self.assertRaises(LoginRejected):
            self.flow.complete(state=begin.state,browser_binding='a'*43,code='valid-code-value-1')
        self.assertEqual(len(self.store.pending),1)
    def test_wrong_state_denied(self):
        begin,_=self.start()
        with self.assertRaises(LoginRejected):
            self.flow.complete(state='b'*43,browser_binding=begin.browser_binding,code='valid-code-value-1')
    def test_nonce_mismatch_denied(self):
        begin,_=self.start()
        self.claim_override['nonce']='tampered-nonce'
        with self.assertRaises(LoginRejected):
            self.flow.complete(state=begin.state,browser_binding=begin.browser_binding,code='valid-code-value-1')
        self.assertEqual(self.store.sessions,{})
    def test_missing_nonce_denied(self):
        begin,_=self.start()
        self.claim_override['nonce']=None
        with self.assertRaises(LoginRejected):
            self.flow.complete(state=begin.state,browser_binding=begin.browser_binding,code='valid-code-value-1')
    def test_unregistered_identity_denied(self):
        begin,_=self.start()
        self.claim_override['sub']='stranger'
        with self.assertRaises(LoginRejected):
            self.flow.complete(state=begin.state,browser_binding=begin.browser_binding,code='valid-code-value-1')
    def test_single_factor_mfa_denied(self):
        begin,_=self.start()
        self.claim_override['amr']=['pwd']
        with self.assertRaises(LoginRejected):
            self.flow.complete(state=begin.state,browser_binding=begin.browser_binding,code='valid-code-value-1')
    def test_empty_code_denied(self):
        begin,_=self.start()
        with self.assertRaises(LoginRejected):
            self.flow.complete(state=begin.state,browser_binding=begin.browser_binding,code='')
    def test_settings_reject_http(self):
        with self.assertRaises(ValueError):
            OIDCLoginSettings('http://id.example/authorize','https://app.example/callback',self.config)
    def test_two_transactions_are_distinct(self):
        a,p1=self.start()
        b,p2=self.start()
        self.assertNotEqual(a.state,b.state)
        self.assertNotEqual(a.browser_binding,b.browser_binding)
        self.assertNotEqual(p1['nonce'],p2['nonce'])
