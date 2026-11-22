"""Offline contracts for public provider URLs and the confidential PKCE exchange.

No actual user identity, client secret, internet provider or tenant is contacted.
"""
import json
import unittest
import base64
from datetime import datetime,timezone,timedelta
import jwt
from urllib.parse import urlsplit
from urllib.parse import parse_qs
from unittest.mock import patch
from email.message import Message

from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from sme_partner.oidc_flow import LoginRejected
from sme_partner.oidc_provider import (
    PinnedProvider, ProviderHTTP, ProviderUnavailable, VerifiedProviderClient,
)


def settings(**kwargs):
    spec={
        "issuer":"https://accounts.example.com",
        "authorization_endpoint":"https://login.example.com/oauth/authorize",
        "token_endpoint":"https://oauth.example.net/token",
        "jwks_uri":"https://keys.example.net/jwks",
        "client_id":"test-client",
        "redirect_uri":"https://workspace.example.com/auth/oidc/callback",
        "client_secret":"not-a-real-secret-12345",
    }
    spec.update(kwargs)
    return PinnedProvider(**spec)


class FakeHTTP:
    def __init__(self, responses):
        self.responses=responses
        self.calls=[]
    def request(self, endpoint, *, data=None, headers=None, limit=131072):
        self.calls.append((endpoint,data,headers,limit))
        value=self.responses.get(endpoint,{})
        if isinstance(value,Exception):
            raise value
        return value


class ProviderAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        cls.jwk=json.loads(RSAAlgorithm.to_jwk(cls.key.public_key()))
        cls.jwk.update({"kid":"key-1","use":"sig","alg":"RS256"})

    def metadata(self):
        cfg=settings()
        return {
            "issuer":cfg.issuer,
            "authorization_endpoint":cfg.authorization_endpoint,
            "token_endpoint":cfg.token_endpoint,
            "jwks_uri":cfg.jwks_uri,
            "response_types_supported":["code"],
            "id_token_signing_alg_values_supported":["RS256"],
            "code_challenge_methods_supported":["S256"],
        }

    def test_different_pinned_hosts_supported(self):
        p=settings()
        self.assertNotEqual(p.issuer,p.token_endpoint)
        self.assertEqual(p.token_endpoint,"https://oauth.example.net/token")

    def test_invalid_config_and_redirect_fail_closed(self):
        cases=[
            {"issuer":"http://accounts.example.com"},
            {"token_endpoint":"http://localhost/token"},
            {"token_endpoint":"https://a.example@evil.example/token"},
            {"jwks_uri":"https://127.0.0.1/keys"},
            {"authorization_endpoint":"https://login.example.com/auth#fragment"},
            {"redirect_uri":"https://workspace.example.com/other"},
            {"redirect_uri":"https://evil@example.com/auth/oidc/callback"},
            {"client_secret":"short"},
            {"client_id":"with:colon"},
        ]
        for fields in cases:
            with self.subTest(fields=fields),self.assertRaises(ValueError):
                settings(**fields)

    def test_discovery_must_match_pinned_endpoints(self):
        cfg=settings()
        http=FakeHTTP({cfg.issuer+"/.well-known/openid-configuration":self.metadata()})
        client=VerifiedProviderClient(cfg,http)
        client.verify_discovery()
        self.assertEqual(len(http.calls),1)
        bad=self.metadata()
        bad["jwks_uri"]="https://attacker.example/keys"
        http.responses[cfg.issuer+"/.well-known/openid-configuration"]=bad
        with self.assertRaises(ProviderUnavailable):
            client.verify_discovery()
        bad=self.metadata()
        bad["code_challenge_methods_supported"]=["plain"]
        http.responses[cfg.issuer+"/.well-known/openid-configuration"]=bad
        with self.assertRaises(ProviderUnavailable):
            client.verify_discovery()

    def test_jwks_validates_keys_and_supports_rotation_on_new_flow(self):
        cfg=settings()
        http=FakeHTTP({
            cfg.issuer+"/.well-known/openid-configuration":self.metadata(),
            cfg.jwks_uri:{"keys":[self.jwk]},
        })
        client=VerifiedProviderClient(cfg,http)
        flow=client.create_login_flow(store=object())
        self.assertEqual(flow.settings.oidc.jwks["keys"][0]["kid"],"key-1")
        second=dict(self.jwk,kid="key-2")
        http.responses[cfg.jwks_uri]={"keys":[second]}
        reloaded=client.create_login_flow(store=object())
        self.assertEqual(reloaded.settings.oidc.jwks["keys"][0]["kid"],"key-2")
        http.responses[cfg.jwks_uri]={"keys":[self.jwk,dict(self.jwk)]}
        with self.assertRaises(ProviderUnavailable):
            client.create_login_flow(store=object())
        http.responses[cfg.jwks_uri]={"keys":[dict(self.jwk,alg="HS256")]}
        with self.assertRaises(ProviderUnavailable):
            client.fetch_trusted_jwks()

    def test_exchange_pins_redirect_client_and_secret_not_sent_elsewhere(self):
        cfg=settings()
        http=FakeHTTP({cfg.token_endpoint:{"id_token":"x"*100}})
        client=VerifiedProviderClient(cfg,http)
        token=client.exchange_code("c"*32,"v"*48,cfg.redirect_uri,cfg.client_id)
        self.assertEqual(token,"x"*100)
        url,form,headers,limit=http.calls[0]
        self.assertEqual(url,cfg.token_endpoint)
        self.assertEqual(limit,32768)
        values=parse_qs(form.decode())
        self.assertEqual(values["code_verifier"],["v"*48])
        self.assertEqual(values["redirect_uri"],[cfg.redirect_uri])
        self.assertNotIn("client_secret",values)
        self.assertTrue(headers["Authorization"].startswith("Basic "))
        self.assertNotIn(cfg.client_secret,str(values))
        for redirect,clientid in (("https://evil.example/auth/oidc/callback",cfg.client_id),
                                  (cfg.redirect_uri,"attacker")):
            with self.assertRaises(ProviderUnavailable):
                client.exchange_code("c"*32,"v"*48,redirect,clientid)
        self.assertEqual(len(http.calls),1)

    def test_basic_client_credentials_encode_reserved_secret_characters(self):
        cfg=settings(client_secret="synthetic+secret/with space:and=sign")
        http=FakeHTTP({cfg.token_endpoint:{"id_token":"z"*100}})
        VerifiedProviderClient(cfg,http).exchange_code(
            "c"*32,"v"*48,cfg.redirect_uri,cfg.client_id)
        _,_,headers,_=http.calls[0]
        decoded=base64.b64decode(headers["Authorization"].split(" ",1)[1]).decode("ascii")
        self.assertEqual(decoded,"test-client:synthetic%2Bsecret%2Fwith+space%3Aand%3Dsign")

    def test_http_transport_rejects_redirect_and_large_or_invalid_json(self):
        class Response:
            def __init__(self,data,content_type="application/json",status=200):
                self.data=data
                self.status=status
                self.headers={"Content-Type":content_type}
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return self.data[:n]
        adapter=ProviderHTTP()
        class Opener:
            def __init__(self,response):self.response=response
            def open(self,*args,**kwargs):return self.response
        adapter._opener=Opener(Response(b'{"keys":[]}'))
        self.assertEqual(adapter.request("https://keys.example.net/jwks"),{"keys":[]})
        adapter._opener=Opener(Response(b'x'*150000))
        with self.assertRaises(ProviderUnavailable):
            adapter.request("https://keys.example.net/jwks")
        adapter._opener=Opener(Response(b'<html/>',"text/html"))
        with self.assertRaises(ProviderUnavailable):
            adapter.request("https://keys.example.net/jwks")
        adapter._opener=Opener(Response(b'["array"]'))
        with self.assertRaises(ProviderUnavailable):
            adapter.request("https://keys.example.net/jwks")

    def test_transport_keeps_tls_validation_and_rejects_redirects(self):
        adapter=ProviderHTTP()
        self.assertTrue(any(type(x).__name__=="_RejectRedirects"
                            for x in adapter._opener.handlers))
        from urllib.request import Request
        handler=next(x for x in adapter._opener.handlers
                     if type(x).__name__=="_RejectRedirects")
        with self.assertRaises(ProviderUnavailable):
            handler.redirect_request(Request("https://keys.example.net/jwks"),
                                     None,302,"redirect",{},
                                     "https://attacker.example/jwks")

    def test_errors_do_not_expose_secret_in_exception(self):
        cfg=settings()
        http=FakeHTTP({cfg.token_endpoint:ProviderUnavailable("provider unavailable")})
        client=VerifiedProviderClient(cfg,http)
        with self.assertRaises(ProviderUnavailable) as context:
            client.exchange_code("x"*32,"v"*48,cfg.redirect_uri,cfg.client_id)
        self.assertNotIn(cfg.client_secret,str(context.exception))


    def test_unknown_signing_kid_refreshes_pinned_jwks_once_and_fails_closed(self):
        first=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        second=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        def pub(key,kid):
            data=json.loads(RSAAlgorithm.to_jwk(key.public_key()))
            data.update({"kid":kid,"use":"sig","alg":"RS256"})
            return data
        cfg=settings()
        http=FakeHTTP({
            cfg.issuer+"/.well-known/openid-configuration":self.metadata(),
            cfg.jwks_uri:{"keys":[pub(first,"first")]},
        })
        provider=VerifiedProviderClient(cfg,http)
        class Store:
            def __init__(self):self.pending={};self.sessions=[]
            def begin(self,s,b,v,n):self.pending[s]=(b,v,n)
            def consume(self,s,b):
                item=self.pending.pop(s,None)
                return item[1:] if item and item[0]==b else None
            def issue(self,issuer,subject,digest,ttl):
                self.sessions.append((issuer,subject,digest,ttl))
                return True
        store=Store()
        flow=provider.create_login_flow(store)
        from urllib.parse import parse_qs
        started=flow.start()
        nonce=parse_qs(urlsplit(started.authorization_url).query)["nonce"][0]
        now=int(datetime.now(timezone.utc).timestamp())
        claims={"iss":cfg.issuer,"sub":"synthetic-user","aud":cfg.client_id,
                "nonce":nonce,"iat":now,"exp":now+120}
        signed=jwt.encode(claims,second,algorithm="RS256",headers={"kid":"second"})
        http.responses[cfg.jwks_uri]={"keys":[pub(first,"first"),pub(second,"second")]}
        http.responses[cfg.token_endpoint]={"id_token":signed}
        cookie=flow.complete(state=started.state,browser_binding=started.browser_binding,
                             code="synthetic-long-auth-code-123")
        self.assertEqual(len(cookie),43)
        self.assertEqual(len(store.sessions),1)
        self.assertEqual([x[0] for x in http.calls].count(cfg.jwks_uri),2)

        # A second unknown kid within the refresh cooldown must NOT trigger
        # another outbound request or issue any new session.
        third=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        second_login=flow.start()
        nonce2=parse_qs(urlsplit(second_login.authorization_url).query)["nonce"][0]
        http.responses[cfg.token_endpoint]={"id_token":jwt.encode(
            dict(claims,nonce=nonce2),third,algorithm="RS256",headers={"kid":"third"})}
        http.responses[cfg.jwks_uri]={"keys":[pub(third,"third")]}
        with self.assertRaises(LoginRejected):
            flow.complete(state=second_login.state,browser_binding=second_login.browser_binding,
                          code="second-synthetic-auth-code-123")
        self.assertEqual(len(store.sessions),1)
        self.assertEqual([x[0] for x in http.calls].count(cfg.jwks_uri),2)


if __name__=="__main__":
    unittest.main()
