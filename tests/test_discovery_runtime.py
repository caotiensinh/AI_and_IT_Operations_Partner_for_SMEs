"""Operator configuration starts only with pinned provider metadata and independent DB roles."""
import json
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from sme_partner.discovery_runtime import create_configured_discovery_app
from sme_partner.oidc_provider import ProviderUnavailable


def env():
    return {
        "SME_APP_DATABASE_DSN":"postgresql://app_role:app@db.example:5432/sme",
        "SME_AUTH_DATABASE_DSN":"postgresql://auth_role:auth@db.example:5432/sme",
        "SME_TRUSTED_ORIGIN":"https://workspace.example",
        "SME_CSRF_SECRET_HEX":"ab"*32,
        "SME_OIDC_ISSUER":"https://id.example",
        "SME_OIDC_AUTHORIZATION_ENDPOINT":"https://id.example/authorize",
        "SME_OIDC_TOKEN_ENDPOINT":"https://oauth.example/token",
        "SME_OIDC_JWKS_URI":"https://keys.example/jwks",
        "SME_OIDC_CLIENT_ID":"registered-client",
        "SME_OIDC_REDIRECT_URI":"https://workspace.example/auth/oidc/callback",
        "SME_OIDC_CLIENT_SECRET":"secret-only-for-synthetic-test-123",
        "SME_OIDC_REQUIRE_MFA":"false",
    }


class HTTP:
    def __init__(self):
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        self.public=json.loads(RSAAlgorithm.to_jwk(key.public_key()))
        self.public.update({"kid":"synthetic-key","use":"sig","alg":"RS256"})
        self.calls=[]
        self.fail=False
    def request(self,url,**kwargs):
        self.calls.append(url)
        if self.fail:
            raise ProviderUnavailable("provider refused")
        if url=="https://keys.example/jwks":
            return {"keys":[self.public]}
        if url=="https://id.example/.well-known/openid-configuration":
            return {
                "issuer":"https://id.example",
                "authorization_endpoint":"https://id.example/authorize",
                "token_endpoint":"https://oauth.example/token",
                "jwks_uri":"https://keys.example/jwks",
                "response_types_supported":["code"],
                "id_token_signing_alg_values_supported":["RS256"],
                "code_challenge_methods_supported":["S256"],
            }
        raise AssertionError("not a pinned endpoint: "+url)


class ConfiguredRuntimeTests(unittest.TestCase):
    def test_missing_configuration_refuses_start(self):
        with self.assertRaisesRegex(ValueError,"SME_APP_DATABASE_DSN"):
            create_configured_discovery_app({})

    def test_refuses_shared_db_identity_and_weak_csrf(self):
        config=env()
        config["SME_AUTH_DATABASE_DSN"]=config["SME_APP_DATABASE_DSN"]
        with self.assertRaisesRegex(ValueError,"independently provisioned"):
            create_configured_discovery_app(config)
        config=env()
        config["SME_CSRF_SECRET_HEX"]="aa"
        with self.assertRaisesRegex(ValueError,"32 random bytes"):
            create_configured_discovery_app(config)
        config=env()
        config["SME_CSRF_SECRET_HEX"]="badhex"
        with self.assertRaisesRegex(ValueError,"valid hexadecimal"):
            create_configured_discovery_app(config)

    def test_invalid_mfa_and_untrusted_url_fail_before_network(self):
        config=env()
        config["SME_OIDC_REQUIRE_MFA"]="sometimes"
        with self.assertRaisesRegex(ValueError,"true or false"):
            create_configured_discovery_app(config)
        config=env()
        config["SME_OIDC_TOKEN_ENDPOINT"]="http://localhost:8080/token"
        http=HTTP()
        with self.assertRaises(ValueError):
            create_configured_discovery_app(config,provider_http=http)
        self.assertEqual(http.calls,[])

    def test_valid_config_uses_pinned_metadata_without_db_connect(self):
        http=HTTP()
        with patch("sme_partner.discovery_runtime.psycopg.connect",side_effect=AssertionError(
            "No DB connection should open until auth request")):
            app=create_configured_discovery_app(env(),provider_http=http)
        self.assertEqual(app.title,"SME Research Discovery Read API")
        self.assertEqual(http.calls,[
            "https://id.example/.well-known/openid-configuration",
            "https://keys.example/jwks",
        ])

    def test_fail_closed_when_provider_unavailable_and_no_secrets_logged(self):
        http=HTTP()
        http.fail=True
        config=env()
        with self.assertRaises(ProviderUnavailable) as result:
            create_configured_discovery_app(config,provider_http=http)
        self.assertNotIn(config["SME_OIDC_CLIENT_SECRET"],str(result.exception))


if __name__=="__main__":
    unittest.main()
