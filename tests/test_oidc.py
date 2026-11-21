import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from sme_partner.oidc import OIDCConfig, AuthenticationDenied, verify_id_token


class OIDCVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.other_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.jwk = __import__('json').loads(RSAAlgorithm.to_jwk(cls.private.public_key()))
        cls.jwk.update({'kid': 'key1', 'use': 'sig', 'alg': 'RS256'})
        cls.config = OIDCConfig('https://id.example', 'sme-web', {'keys':[cls.jwk]})
        cls.now = datetime.now(timezone.utc)

    def claims(self, **overrides):
        claims = {'iss':'https://id.example','sub':'provider-subject',
                  'aud':'sme-web','exp':int((self.now+timedelta(minutes=5)).timestamp()),
                  'iat':int(self.now.timestamp()),'amr':['pwd','otp']}
        claims.update(overrides)
        return claims

    def sign(self, claims=None, key=None, headers=None):
        return jwt.encode(self.claims() if claims is None else claims,
                          key or self.private, algorithm='RS256',
                          headers=headers or {'kid':'key1'})

    def test_valid_signature_subject(self):
        result=verify_id_token(self.sign(),self.config)
        self.assertEqual(result.subject,'provider-subject')
        self.assertTrue(result.mfa_satisfied)

    def test_wrong_signature_denied(self):
        with self.assertRaises(AuthenticationDenied):
            verify_id_token(self.sign(key=self.other_private),self.config)

    def test_unknown_key_denied(self):
        with self.assertRaises(AuthenticationDenied):
            verify_id_token(self.sign(headers={'kid':'unknown'}),self.config)

    def test_wrong_issuer_denied(self):
        with self.assertRaises(AuthenticationDenied):
            verify_id_token(self.sign(self.claims(iss='https://evil.example')),self.config)

    def test_wrong_audience_denied(self):
        with self.assertRaises(AuthenticationDenied):
            verify_id_token(self.sign(self.claims(aud='evil-client')),self.config)

    def test_expired_denied(self):
        with self.assertRaises(AuthenticationDenied):
            verify_id_token(self.sign(self.claims(exp=int((self.now-timedelta(hours=1)).timestamp()))),self.config)

    def test_future_issued_at_denied(self):
        with self.assertRaises(AuthenticationDenied):
            verify_id_token(self.sign(self.claims(iat=int((self.now+timedelta(hours=1)).timestamp()))),self.config)

    def test_stale_token_denied(self):
        with self.assertRaises(AuthenticationDenied):
            verify_id_token(self.sign(self.claims(iat=int((self.now-timedelta(hours=2)).timestamp()))),self.config)

    def test_missing_sub_denied(self):
        c=self.claims(); del c['sub']
        with self.assertRaises(AuthenticationDenied):verify_id_token(self.sign(c),self.config)

    def test_multiple_audience_requires_azp(self):
        with self.assertRaises(AuthenticationDenied):
            verify_id_token(self.sign(self.claims(aud=['sme-web','another'])),self.config)
        result=verify_id_token(self.sign(self.claims(aud=['sme-web','another'],azp='sme-web')),self.config)
        self.assertEqual(result.audience,'sme-web')

    def test_mfa_policy(self):
        required=OIDCConfig('https://id.example','sme-web',{'keys':[self.jwk]},require_mfa=True)
        with self.assertRaises(AuthenticationDenied):
            verify_id_token(self.sign(self.claims(amr=['pwd'])),required)
        self.assertTrue(verify_id_token(self.sign(),required).mfa_satisfied)

    def test_mfa_acr_allowlist(self):
        required=OIDCConfig('https://id.example','sme-web',{'keys':[self.jwk]},require_mfa=True,accepted_acr=frozenset({'urn:provider:strong'}))
        self.assertTrue(verify_id_token(self.sign(self.claims(amr=[],acr='urn:provider:strong')),required).mfa_satisfied)

    def test_token_header_jku_denied(self):
        with self.assertRaises(AuthenticationDenied):
            verify_id_token(self.sign(headers={'kid':'key1','jku':'https://attacker.example/jwks'}),self.config)

    def test_missing_kid_denied(self):
        with self.assertRaises(AuthenticationDenied):
            verify_id_token(self.sign(headers={'typ':'JWT'}),self.config)

    def test_oversized_token_denied(self):
        with self.assertRaises(AuthenticationDenied):
            verify_id_token('a'*20000,self.config)

    def test_unconfigured_mfa_acr_is_not_trusted(self):
        required=OIDCConfig('https://id.example','sme-web',{'keys':[self.jwk]},require_mfa=True)
        with self.assertRaises(AuthenticationDenied):
            verify_id_token(self.sign(self.claims(amr=[],acr='unverified')),required)


if __name__=='__main__': unittest.main()
