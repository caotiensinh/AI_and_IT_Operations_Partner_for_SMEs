"""Strict, offline JWKS-backed OIDC ID-token verification for login bootstrap.

IMPORTANT: ID tokens are not API bearer tokens. The verified subject must be
mapped to an internal identity via a trusted server-side database lookup.
Never accept tenant membership, roles, or scopes from token claims.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import jwt
import hmac
from jwt.algorithms import RSAAlgorithm
from jwt.exceptions import PyJWTError


class AuthenticationDenied(PermissionError):
    """Uniform externally safe authentication failure."""


@dataclass(frozen=True, slots=True)
class OIDCConfig:
    issuer: str
    client_id: str
    jwks: dict[str, Any]
    require_mfa: bool = False
    accepted_acr: frozenset[str] = frozenset()
    max_token_age_seconds: int = 900
    leeway_seconds: int = 30

    def __post_init__(self) -> None:
        if not self.issuer.startswith("https://") or not self.client_id:
            raise ValueError("OIDC issuer must be HTTPS and client ID non-empty")
        if self.max_token_age_seconds <= 0 or not 0 <= self.leeway_seconds <= 120:
            raise ValueError("invalid OIDC lifetime or clock skew")
        keys = self.jwks.get("keys")
        if not isinstance(keys, list) or not keys:
            raise ValueError("trusted JWKS must contain keys")


@dataclass(frozen=True, slots=True)
class VerifiedOIDCSubject:
    issuer: str
    subject: str
    audience: str
    authenticated_at: int
    expires_at: int
    mfa_satisfied: bool
    authentication_time: int | None = None


def verify_id_token(token: str, config: OIDCConfig, *, now: datetime | None = None, expected_nonce: str | None = None) -> VerifiedOIDCSubject:
    """Verify RS256 signatures and OIDC claims against *trusted pinned* JWKS.

    The JWKS must be fetched/refreshed from a pinned provider configuration by
    trusted infrastructure, never using jku/x5u/jwks_uri from a token header.
    """
    if not isinstance(token, str) or len(token) > 16384 or token.count(".") != 2:
        raise AuthenticationDenied("invalid token")
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    timestamp = int(clock.timestamp())
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
            raise AuthenticationDenied("unsupported signing key")
        if any(key in header for key in ("jku", "x5u", "jwk", "crit")):
            raise AuthenticationDenied("untrusted key reference")
        kid = header["kid"]
        matching = [key for key in config.jwks["keys"]
                    if key.get("kid") == kid and key.get("kty") == "RSA"
                    and key.get("use", "sig") == "sig"
                    and key.get("alg", "RS256") == "RS256"]
        if len(matching) != 1:
            raise AuthenticationDenied("signing key unavailable")
        public_key = RSAAlgorithm.from_jwk(matching[0])
        claims = jwt.decode(
            token, public_key, algorithms=["RS256"],
            audience=config.client_id, issuer=config.issuer,
            leeway=config.leeway_seconds,
            options={"require": ["iss", "sub", "aud", "exp", "iat"],
                     "verify_iat": True, "verify_exp": True,
                     "verify_nbf": True},
            # Current time is controlled by PyJWT internally; explicit temporal
            # checks below allow deterministic boundary tests and future clocks.
        )
        if expected_nonce is not None:
            nonce = claims.get("nonce")
            if not isinstance(nonce, str) or not hmac.compare_digest(nonce, expected_nonce):
                raise AuthenticationDenied("invalid login nonce")
        sub = claims["sub"]
        issued_at = claims["iat"]
        expires_at = claims["exp"]
        aud = claims["aud"]
        if not isinstance(sub, str) or not sub or len(sub) > 255:
            raise AuthenticationDenied("invalid subject")
        if type(issued_at) is not int or type(expires_at) is not int:
            raise AuthenticationDenied("invalid token timestamp")
        if timestamp < issued_at - config.leeway_seconds:
            raise AuthenticationDenied("token from future")
        if timestamp > expires_at + config.leeway_seconds:
            raise AuthenticationDenied("expired token")
        if timestamp - issued_at > config.max_token_age_seconds + config.leeway_seconds:
            raise AuthenticationDenied("stale login token")
        if isinstance(aud, list):
            if len(aud) > 1 and claims.get("azp") != config.client_id:
                raise AuthenticationDenied("authorized party mismatch")
        elif not isinstance(aud, str):
            raise AuthenticationDenied("invalid audience")
        if "azp" in claims and claims["azp"] != config.client_id:
            raise AuthenticationDenied("authorized party mismatch")
        amr = claims.get("amr", [])
        amr_set = set(method for method in amr if isinstance(method, str)) if isinstance(amr, list) else set()
        # Do not treat a single OTP / hardware key alone as evidence of MFA.
        amr_ok = "mfa" in amr_set or ("pwd" in amr_set and bool(
            amr_set & {"otp", "hwk", "swk", "webauthn"}))
        acr_ok = (isinstance(claims.get("acr"), str)
                  and claims["acr"] in config.accepted_acr)
        has_mfa = amr_ok or acr_ok
        auth_time = claims.get("auth_time")
        if auth_time is not None:
            if type(auth_time) is not int or auth_time < 0:
                raise AuthenticationDenied("invalid authentication time")
            if auth_time > timestamp + config.leeway_seconds:
                raise AuthenticationDenied("future authentication time")
            if auth_time > issued_at + config.leeway_seconds:
                raise AuthenticationDenied("authentication after token issuance")
        if config.require_mfa and not has_mfa:
            raise AuthenticationDenied("required MFA not satisfied")
        return VerifiedOIDCSubject(
            issuer=config.issuer, subject=sub, audience=config.client_id,
            authenticated_at=issued_at, expires_at=expires_at,
            mfa_satisfied=has_mfa, authentication_time=auth_time,
        )
    except AuthenticationDenied:
        raise
    except (PyJWTError, ValueError, TypeError, KeyError) as exc:
        raise AuthenticationDenied("invalid identity token") from None
