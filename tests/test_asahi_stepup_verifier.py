"""Spec 020: signed fresh-MFA assertion; synthetic offline IdP only."""
import json
import unittest
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from sme_partner.asahi_stepup_verifier import verify_fresh_stepup
from sme_partner.oidc import AuthenticationDenied, OIDCConfig


class FreshStepupVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private = rsa.generate_private_key(public_exponent=65537,key_size=2048)
        cls.foreign_private = rsa.generate_private_key(public_exponent=65537,key_size=2048)
        key=json.loads(RSAAlgorithm.to_jwk(cls.private.public_key()))
        key.update({"kid":"pinned","use":"sig","alg":"RS256"})
        cls.config=OIDCConfig("https://id.example","sme-web",{"keys":[key]})
        cls.nonce="n"*43

    def setUp(self):
        self.now=datetime.now(timezone.utc).replace(microsecond=0)

    def claims(self, **override):
        t=int(self.now.timestamp())
        data={"iss":"https://id.example","sub":"owner-123","aud":"sme-web",
              "iat":t,"exp":t+300,"auth_time":t-10,
              "amr":["pwd","otp"],"nonce":self.nonce}
        data.update(override)
        return data

    def sign(self, claims=None, key=None):
        return jwt.encode(claims or self.claims(),key or self.private,
                          algorithm="RS256",headers={"kid":"pinned"})

    def verify(self, claims=None, token=None, **kwargs):
        return verify_fresh_stepup(
            token or self.sign(claims),self.config,
            expected_issuer="https://id.example",
            expected_subject="owner-123",
            expected_nonce=self.nonce,
            now=self.now,**kwargs)

    def denied(self, claims=None, token=None, **kwargs):
        with self.assertRaises(AuthenticationDenied):
            self.verify(claims,token,**kwargs)

    def test_accepts_fresh_real_auth_time_and_mfa(self):
        result=self.verify()
        self.assertEqual(result.subject,"owner-123")
        self.assertEqual(result.authenticated_at,int(self.now.timestamp())-10)

    def test_iat_is_not_auth_time(self):
        t=int(self.now.timestamp())
        self.denied(self.claims(auth_time=t-121))
        claims=self.claims()
        del claims["auth_time"]
        self.denied(claims)

    def test_rejects_single_factor_and_unknown_acr(self):
        self.denied(self.claims(amr=["pwd"]))
        self.denied(self.claims(amr=["otp"]))
        self.denied(self.claims(amr=[],acr="unspecified"))

    def test_rejects_wrong_account_nonce_and_issuer(self):
        self.denied(self.claims(sub="other-owner"))
        self.denied(self.claims(iss="https://other.example"))
        self.denied(self.claims(nonce="x"*43))

    def test_rejects_untrusted_signature_and_unsigned_token(self):
        self.denied(token=self.sign(key=self.foreign_private))
        self.denied(token="not.a.jwt")

    def test_rejects_future_invalid_and_boundary_auth_time(self):
        t=int(self.now.timestamp())
        self.denied(self.claims(auth_time=t+1))
        self.denied(self.claims(auth_time=True))
        self.denied(self.claims(auth_time="recent"))
        self.denied(self.claims(auth_time=-1))
        self.denied(self.claims(auth_time=t+31))
        self.assertEqual(self.verify(self.claims(auth_time=t-120)).subject,"owner-123")
        self.denied(self.claims(auth_time=t-121))

    def test_fails_closed_without_challenge_and_invalid_config(self):
        with self.assertRaises(AuthenticationDenied):
            verify_fresh_stepup(self.sign(),self.config,
                expected_issuer="https://id.example",expected_subject="owner-123",
                expected_nonce="short",now=self.now)
        with self.assertRaises(ValueError):
            self.verify(max_auth_age_seconds=121)
        with self.assertRaises(ValueError):
            self.verify(max_auth_age_seconds=0)
        with self.assertRaises(ValueError):
            self.verify(max_auth_age_seconds=True)
        with self.assertRaises(ValueError):
            self.verify(now=datetime.now().replace(tzinfo=None))

    def test_stale_token_and_expiration(self):
        t=int(self.now.timestamp())
        self.denied(self.claims(iat=t-1800,auth_time=t-10))
        self.denied(self.claims(exp=t-3600,auth_time=t-10))


if __name__=="__main__":
    unittest.main()
