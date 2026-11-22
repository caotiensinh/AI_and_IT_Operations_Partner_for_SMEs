"""Strict MFA attestation verification for *trusted* Asahi step-up service.

This is a verifier component, not a browser endpoint and never calls the proof
issuer. A trusted upstream must atomically consume the browser-bound challenge,
fetch the expected issuer/subject from PostgreSQL, and exchange OIDC code with a
pinned provider; the account's existing session is not MFA proof.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hmac

from .oidc import AuthenticationDenied, OIDCConfig, verify_id_token


@dataclass(frozen=True, slots=True)
class VerifiedFreshStepup:
    issuer: str
    subject: str
    authenticated_at: int


def verify_fresh_stepup(
    id_token: str,
    config: OIDCConfig,
    *,
    expected_issuer: str,
    expected_subject: str,
    expected_nonce: str,
    now: datetime | None = None,
    max_auth_age_seconds: int = 120,
) -> VerifiedFreshStepup:
    """Verify signed ID token, fresh explicit auth_time, MFA and account binding.

    'iat' alone is never evidence of fresh reauthentication. The caller MUST
    derive expected_issuer/subject from a tenant-scoped active DB session and
    expected_nonce from a single-use, browser-bound OIDC challenge.
    """
    if not isinstance(expected_nonce, str) or not 32 <= len(expected_nonce) <= 128:
        raise AuthenticationDenied("invalid step-up challenge")
    if not isinstance(expected_issuer, str) or not expected_issuer:
        raise AuthenticationDenied("invalid expected identity")
    if not isinstance(expected_subject, str) or not expected_subject:
        raise AuthenticationDenied("invalid expected identity")
    if type(max_auth_age_seconds) is not int or not 1 <= max_auth_age_seconds <= 120:
        raise ValueError("invalid step-up maximum authentication age")
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    # Reuse the pinned RS256/JWKS, issuer/audience, nonce and strict MFA checks.
    trusted = replace(config, require_mfa=True)
    verified = verify_id_token(
        id_token, trusted, now=clock, expected_nonce=expected_nonce
    )
    if not (hmac.compare_digest(verified.issuer, expected_issuer)
            and hmac.compare_digest(verified.subject, expected_subject)):
        raise AuthenticationDenied("session identity mismatch")
    authentication_time = verified.authentication_time
    if authentication_time is None:
        raise AuthenticationDenied("missing authentication time")
    age = (clock - datetime.fromtimestamp(authentication_time, timezone.utc)).total_seconds()
    # No clock-skew allowance for fresh-auth policy; fail closed at both edges.
    if age < 0 or age > max_auth_age_seconds:
        raise AuthenticationDenied("step-up authentication not fresh")
    return VerifiedFreshStepup(
        issuer=verified.issuer, subject=verified.subject,
        authenticated_at=authentication_time,
    )
