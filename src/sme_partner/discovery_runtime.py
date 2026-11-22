"""Operator-configured SME Discovery cookie BFF application factory.

No production configuration, IdP credentials or application session secret
is committed to this repository. The app refuses to start unless all required
settings and independent database credentials are provided by an operator.
"""
from __future__ import annotations

import os
from collections.abc import Mapping

import psycopg

from .discovery_bff import create_cookie_discovery_app
from .oidc_flow import PostgresLoginStore
from .oidc_provider import PinnedProvider, ProviderHTTP, VerifiedProviderClient


_REQUIRED = (
    "SME_APP_DATABASE_DSN", "SME_AUTH_DATABASE_DSN",
    "SME_TRUSTED_ORIGIN", "SME_CSRF_SECRET_HEX",
    "SME_OIDC_ISSUER", "SME_OIDC_AUTHORIZATION_ENDPOINT",
    "SME_OIDC_TOKEN_ENDPOINT", "SME_OIDC_JWKS_URI",
    "SME_OIDC_CLIENT_ID", "SME_OIDC_REDIRECT_URI",
    "SME_OIDC_CLIENT_SECRET",
)


def create_configured_discovery_app(
    env: Mapping[str, str] | None = None,
    *, provider_http: ProviderHTTP | None = None,
):
    """Construct the cookie-only BFF using provider and DB credentials from config.

    Must run behind trusted TLS reverse proxy; external IdP traffic always
    verifies normal CA trust and uses the operator-pinned issuer/endpoints.
    """
    values = env if env is not None else os.environ
    absent = [key for key in _REQUIRED if not values.get(key)]
    if absent:
        # Names are safe to diagnose; never log the values.
        raise ValueError("Missing required configuration keys: " + ", ".join(absent))
    if values["SME_APP_DATABASE_DSN"] == values["SME_AUTH_DATABASE_DSN"]:
        raise ValueError("App and OIDC auth DB connections must be independently provisioned")
    try:
        secret = bytes.fromhex(values["SME_CSRF_SECRET_HEX"])
    except ValueError:
        raise ValueError("SME_CSRF_SECRET_HEX must be valid hexadecimal") from None
    if len(secret) < 32:
        raise ValueError("CSRF secret must contain at least 32 random bytes")
    require_mfa = values.get("SME_OIDC_REQUIRE_MFA", "true").lower()
    if require_mfa not in ("true", "false"):
        raise ValueError("SME_OIDC_REQUIRE_MFA must be true or false")
    accepted_acr = frozenset(filter(None, (
        x.strip() for x in values.get("SME_OIDC_ACCEPTED_ACR", "").split(",")
    )))
    provider = VerifiedProviderClient(
        PinnedProvider(
            issuer=values["SME_OIDC_ISSUER"],
            authorization_endpoint=values["SME_OIDC_AUTHORIZATION_ENDPOINT"],
            token_endpoint=values["SME_OIDC_TOKEN_ENDPOINT"],
            jwks_uri=values["SME_OIDC_JWKS_URI"],
            client_id=values["SME_OIDC_CLIENT_ID"],
            redirect_uri=values["SME_OIDC_REDIRECT_URI"],
            client_secret=values["SME_OIDC_CLIENT_SECRET"],
            require_mfa=(require_mfa == "true"),
            accepted_acr=accepted_acr,
        ),
        http=provider_http,
    )
    # Perform pinned metadata/JWKS validation at startup, not on user request.
    # A provider outage or invalid trust metadata blocks startup.
    def app_connect():
        return psycopg.connect(values["SME_APP_DATABASE_DSN"])

    def auth_connect():
        return psycopg.connect(values["SME_AUTH_DATABASE_DSN"])

    flow = provider.create_login_flow(PostgresLoginStore(auth_connect))
    return create_cookie_discovery_app(
        app_connect,csrf_secret=secret,
        trusted_origin=values["SME_TRUSTED_ORIGIN"],oidc_flow=flow,
    )
