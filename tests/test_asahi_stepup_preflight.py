"""Spec 024: deployment preflight must fail closed on credentials and grants."""
import unittest
import json
from dataclasses import replace
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from sme_partner.asahi_stepup_preflight import (
    PreflightDenied, StepupProductionConfig, verify_production_stepup_connections
)
from sme_partner.oidc import OIDCConfig


ISSUER_DSN = "postgresql://stepup_issuer:one@db.example:5432/sme?sslmode=verify-full"
APPROVAL_DSN = "postgresql://stepup_approval:two@db.example:5432/sme?sslmode=verify-full"


class FakeConn:
    def __init__(self, row):
        self.row = row
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, sql):
        assert "has_function_privilege" in sql
        return self
    def fetchone(self): return self.row


class DeploymentGateTests(unittest.TestCase):
    def setUp(self):
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        jwk=json.loads(RSAAlgorithm.to_jwk(key.public_key()))
        jwk.update({"kid":"pinned","alg":"RS256","use":"sig"})
        self.config=StepupProductionConfig(
            public_origin="https://app.example",
            authorization_endpoint="https://id.example/authorize",
            token_endpoint="https://id.example/token",
            redirect_uri="https://app.example/auth/asahi/stepup/callback",
            oidc=OIDCConfig("https://id.example","sme-web",
                {"keys":[jwk]}),
            csrf_key=b"k"*32,
            issuer_database_dsn=ISSUER_DSN,
            approval_database_dsn=APPROVAL_DSN,
            provider_mfa_contract_reviewed=True,
            ingress_tls_reviewed=True,
            distributed_rate_limit_reviewed=True,
            secret_provisioning_reviewed=True,
        )
        self.issuer=("stepup_login","stepup_login",False,
                     True,False,True,True,False,False,False)
        self.approval=("approval_login","approval_login",False,
                       False,True,False,False,False,False,False)
    def run_gate(self, issuer=None, approval=None, config=None):
        verify_production_stepup_connections(
            config or self.config,
            lambda:FakeConn(self.issuer if issuer is None else issuer),
            lambda:FakeConn(self.approval if approval is None else approval)
        )
    def test_positive_isolated_roles(self):
        self.run_gate()
    def test_missing_operator_reviews_are_denied(self):
        for name in (
            "provider_mfa_contract_reviewed","ingress_tls_reviewed",
            "distributed_rate_limit_reviewed","secret_provisioning_reviewed"
        ):
            with self.subTest(name=name),self.assertRaises(PreflightDenied):
                self.run_gate(config=replace(self.config,**{name:False}))
    def test_invalid_urls_and_provider_mismatch_denied(self):
        for name,value in (
            ("public_origin","http://app.example"),
            ("public_origin","https://localhost"),
            ("public_origin","https://app.example/invalid"),
            ("authorization_endpoint","https://attacker.example/authorize"),
            ("token_endpoint","https://attacker.example/token"),
            ("redirect_uri","https://app.example/other-callback"),
            ("redirect_uri","https://another.example/auth/asahi/stepup/callback"),
        ):
            with self.subTest(name=name,value=value),self.assertRaises(PreflightDenied):
                self.run_gate(config=replace(self.config,**{name:value}))
    def test_invalid_credentials_and_secret_denied(self):
        for name,value in (
            ("csrf_key",b"x"),
            ("issuer_database_dsn",APPROVAL_DSN),
            ("issuer_database_dsn","postgresql://a:b@db.example/sme"),
            ("approval_database_dsn","postgresql://bad"),
        ):
            with self.subTest(name=name),self.assertRaises(PreflightDenied):
                self.run_gate(config=replace(self.config,**{name:value}))
    def test_untrusted_jwks_rejected(self):
        for keys in (
            [], [{"kty":"oct","kid":"bad"}],
            [{"kty":"RSA","kid":"bad","alg":"HS256"}]
        ):
            config=replace(self.config,oidc=replace(self.config.oidc,jwks={"keys":keys}))
            with self.subTest(keys=keys),self.assertRaises(PreflightDenied):
                self.run_gate(config=config)
    def test_privileged_or_shared_db_roles_denied(self):
        with self.assertRaises(PreflightDenied):
            self.run_gate(issuer=tuple(["stepup_login","stepup_login",True]+list(self.issuer[3:])))
        with self.assertRaises(PreflightDenied):
            self.run_gate(approval=tuple(["stepup_login","stepup_login"]+list(self.approval[2:])))
        with self.assertRaises(PreflightDenied):
            self.run_gate(issuer=tuple(["stepup_login","postgres"]+list(self.issuer[2:])))
    def test_extra_cross_function_or_direct_table_access_denied(self):
        for index in (4,7,8,9):
            modified=list(self.issuer);modified[index]=True
            with self.subTest(role="issuer",index=index),self.assertRaises(PreflightDenied):
                self.run_gate(issuer=tuple(modified))
        for index in (3,5,6,7,8,9):
            modified=list(self.approval);modified[index]=True
            with self.subTest(role="approval",index=index),self.assertRaises(PreflightDenied):
                self.run_gate(approval=tuple(modified))
    def test_required_function_missing_or_failed_inspection_denied(self):
        modified=list(self.issuer);modified[3]=False
        with self.assertRaises(PreflightDenied):
            self.run_gate(issuer=tuple(modified))
        with self.assertRaises(PreflightDenied):
            self.run_gate(issuer=())
        with self.assertRaises(PreflightDenied):
            verify_production_stepup_connections(
                self.config, lambda:(_ for _ in ()).throw(RuntimeError("secret error")),
                lambda: FakeConn(self.approval))
    def test_same_factory_rejected(self):
        factory=lambda:FakeConn(self.issuer)
        with self.assertRaises(PreflightDenied):
            verify_production_stepup_connections(self.config,factory,factory)


if __name__ == "__main__":
    unittest.main()
