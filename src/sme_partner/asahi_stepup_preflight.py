"""Fail-closed deployment preflight for the *opt-in* Asahi MFA approval BFF.

A check result is only a startup prerequisite, never an authorization grant.
Never log secrets or connection URLs. The deployment owner must independently
validate ingress, rate limiting, IdP semantics and actual MFA acceptance.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit
from collections.abc import Callable
import hashlib
import hmac

from .oidc import OIDCConfig


class PreflightDenied(RuntimeError):
    """The gate must remain OFF if any deployment assumption is unproven."""


def _https_endpoint(value: str, *, origin: bool = False) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise PreflightDenied("invalid HTTPS endpoint")
    parts = urlsplit(value)
    if (parts.scheme != "https" or not parts.hostname or parts.username
        or parts.password or parts.fragment or parts.query):
        raise PreflightDenied("invalid HTTPS endpoint")
    if origin and parts.path not in ("", "/"):
        raise PreflightDenied("invalid HTTPS origin")
    if parts.hostname in ("localhost", "127.0.0.1", "::1") or parts.hostname.endswith(".localhost"):
        raise PreflightDenied("loopback host is not a production origin")
    return value.rstrip("/") if origin else value


@dataclass(frozen=True, slots=True)
class StepupProductionConfig:
    public_origin: str
    authorization_endpoint: str
    token_endpoint: str
    redirect_uri: str
    oidc: OIDCConfig
    csrf_key: bytes
    issuer_database_dsn: str
    approval_database_dsn: str
    provider_mfa_contract_reviewed: bool = False
    ingress_tls_reviewed: bool = False
    distributed_rate_limit_reviewed: bool = False
    secret_provisioning_reviewed: bool = False

    def validate(self) -> None:
        origin = _https_endpoint(self.public_origin, origin=True)
        authorization = _https_endpoint(self.authorization_endpoint)
        token = _https_endpoint(self.token_endpoint)
        callback = _https_endpoint(self.redirect_uri)
        _https_endpoint(self.oidc.issuer)
        if urlsplit(callback).netloc != urlsplit(origin).netloc:
            raise PreflightDenied("OIDC callback must use public origin")
        if urlsplit(callback).path != "/auth/asahi/stepup/callback":
            raise PreflightDenied("step-up callback path mismatch")
        if urlsplit(authorization).netloc != urlsplit(self.oidc.issuer).netloc:
            raise PreflightDenied("OIDC authorization origin is unpinned")
        if urlsplit(token).netloc != urlsplit(self.oidc.issuer).netloc:
            raise PreflightDenied("OIDC token endpoint origin is unpinned")
        if not self.oidc.client_id or self.oidc.client_id.strip() != self.oidc.client_id:
            raise PreflightDenied("invalid OIDC client")
        if not self.oidc.jwks.get("keys") or not all(
            isinstance(key, dict) and key.get("kty") == "RSA"
            and key.get("alg", "RS256") == "RS256"
            and key.get("use", "sig") == "sig"
            and isinstance(key.get("kid"), str) and key["kid"]
            and isinstance(key.get("n"), str) and len(key["n"]) >= 300
            and isinstance(key.get("e"), str) and key["e"] in ("AQAB","Aw")
            for key in self.oidc.jwks.get("keys", [])
        ):
            raise PreflightDenied("pinned RS256 JWKS required")
        if not isinstance(self.csrf_key, bytes) or len(self.csrf_key) < 32:
            raise PreflightDenied("dedicated CSRF key required")
        for dsn in (self.issuer_database_dsn, self.approval_database_dsn):
            if not isinstance(dsn, str) or len(dsn) < 24:
                raise PreflightDenied("separate DB principals required")
            # Production DB principals MUST be authenticated over TLS.
            parsed = urlsplit(dsn)
            if (parsed.scheme != "postgresql" or not parsed.hostname or
                not parsed.username or not parsed.password or
                parsed.fragment or parsed.path != "/sme"):
                raise PreflightDenied("invalid PostgreSQL connection")
            from urllib.parse import parse_qs
            params = parse_qs(parsed.query, keep_blank_values=True)
            if params.get("sslmode") != ["verify-full"]:
                raise PreflightDenied("verified PostgreSQL TLS required")
        if hmac.compare_digest(
            hashlib.sha256(self.issuer_database_dsn.encode()).digest(),
            hashlib.sha256(self.approval_database_dsn.encode()).digest()
        ):
            raise PreflightDenied("issuer and approval connections must differ")
        gates = (
            self.provider_mfa_contract_reviewed,
            self.ingress_tls_reviewed,
            self.distributed_rate_limit_reviewed,
            self.secret_provisioning_reviewed,
        )
        if any(type(flag) is not bool or not flag for flag in gates):
            raise PreflightDenied("production security review not complete")


# Verify grants from the *actual configured runtime connection*, NOT a database
# administrator's SET ROLE simulation. Disallow privileged session_user.
_ROLE_SQL = """
SELECT current_user, session_user,
       (SELECT rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb
        FROM pg_roles WHERE rolname=session_user),
       has_function_privilege(current_user,
          'sme.issue_asahi_stepup(bytea,uuid,text,text,text,text,integer)', 'EXECUTE'),
       has_function_privilege(current_user,
          'sme.approve_asahi_delivery_stepup(bytea,uuid,uuid,text,text,text)', 'EXECUTE'),
       has_function_privilege(current_user,
          'sme.begin_asahi_stepup_challenge(bytea,bytea,bytea,uuid,text,text,text,text,text,text)', 'EXECUTE'),
       has_function_privilege(current_user,
          'sme.resolve_asahi_stepup_identity(bytea,uuid)', 'EXECUTE'),
       has_table_privilege(current_user,'sme.sessions','SELECT'),
       has_table_privilege(current_user,'sme.asahi_stepup_proofs','INSERT'),
       has_table_privilege(current_user,'sme.asahi_delivery_destinations','UPDATE')
"""


def verify_production_stepup_connections(
    config: StepupProductionConfig,
    issuer_connect: Callable,
    approval_connect: Callable,
) -> None:
    """Validate configuration and live DB permission asymmetry before enabling.

    A reviewed checkbox is operator policy input, not an automated assertion
    that a provider or load balancer is secure. A caller must fail closed.
    """
    config.validate()
    if not callable(issuer_connect) or not callable(approval_connect) or issuer_connect is approval_connect:
        raise PreflightDenied("distinct DB connection factories required")
    try:
        observations = []
        for connect in (issuer_connect, approval_connect):
            with connect() as conn:
                row = conn.execute(_ROLE_SQL).fetchone()
                observations.append(row)
    except Exception:
        raise PreflightDenied("database preflight failed") from None
    if any(row is None or len(row) != 10 for row in observations):
        raise PreflightDenied("database permission inspection incomplete")
    issuer, approval = observations
    if (issuer[0] == approval[0] or issuer[1] == approval[1]
        or any(row[2] is not False for row in observations)
        or any(row[1] in ("postgres","sme_app","sme_auth","sme_dispatch",
                           "sme_ingest","sme_approval","sme_stepup")
               for row in observations)):
        raise PreflightDenied("service roles are shared or privileged")
    # index 3: proof issuance, 4: apply approval, 5: challenge start,
    # 6: DB-bound identity lookup, 7-9: forbidden direct table access.
    if tuple(issuer[3:]) != (True, False, True, True, False, False, False):
        raise PreflightDenied("issuer privilege boundary failed")
    if tuple(approval[3:]) != (False, True, False, False, False, False, False):
        raise PreflightDenied("approval privilege boundary failed")
