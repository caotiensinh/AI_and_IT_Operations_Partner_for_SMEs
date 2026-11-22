"""Strict, provider-neutral HTTPS OIDC metadata/JWKS and token exchange.

Operator supplies a fixed issuer, client registration and Secret Manager-backed
client secret. No untrusted URL from a browser, JWT header or discovery response
can redirect outbound traffic to a different origin. Token exchange follows no
redirects, validates HTTPS, and caps response bytes.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import re
import ssl
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlencode, quote_plus
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from .oidc import OIDCConfig
from jwt.algorithms import RSAAlgorithm
from .oidc_flow import OIDCLoginFlow, OIDCLoginSettings, LoginStore

MAX_JSON_BYTES = 131_072
MAX_TOKEN_BYTES = 32_768
SAFE_SEGMENT = re.compile(r"^[a-zA-Z0-9._~-]+$")


class ProviderUnavailable(RuntimeError):
    """Non-sensitive, externally safe provider failure."""


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ProviderUnavailable("identity provider endpoint redirect refused")


def _https_endpoint(value: str, *, required_host: str | None = None) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("invalid OIDC URL")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname
            or parsed.username or parsed.password or parsed.fragment
            or parsed.query or parsed.port is None and ":" in parsed.netloc
            or parsed.hostname in ("localhost", "127.0.0.1", "::1")):
        raise ValueError("OIDC endpoint must be a trusted public HTTPS URL")
    if required_host and parsed.hostname.lower() != required_host.lower():
        raise ValueError("OIDC endpoint host not allowlisted")
    return value


@dataclass(frozen=True)
class PinnedProvider:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    client_id: str
    redirect_uri: str
    client_secret: str
    require_mfa: bool = False
    accepted_acr: frozenset[str] = frozenset()

    def __post_init__(self):
        issuer = _https_endpoint(self.issuer)
        issuer_parts = urlsplit(issuer)
        if issuer.endswith("/") or issuer_parts.query:
            raise ValueError("issuer must be exact non-query URL without trailing slash")
        for name in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            _https_endpoint(getattr(self, name))
        callback = urlsplit(self.redirect_uri)
        if (callback.scheme != "https" or not callback.hostname
                or callback.username or callback.password or callback.query
                or callback.fragment or not callback.path.startswith("/auth/oidc/")):
            raise ValueError("redirect_uri must be trusted HTTPS application callback")
        if not self.client_id or len(self.client_id) > 256 or ":" in self.client_id:
            raise ValueError("invalid client registration")
        if not self.client_secret or len(self.client_secret) < 16:
            raise ValueError("confidential OIDC client secret required")
        if not all(isinstance(acr, str) and acr for acr in self.accepted_acr):
            raise ValueError("invalid ACR policy")


class ProviderHTTP:
    """Real TLS-verified transport; redirect rejection is enforced on all requests."""

    def __init__(self, *, timeout_seconds: float = 5.0):
        if not 0.5 <= timeout_seconds <= 15:
            raise ValueError("identity provider timeout outside bounds")
        self.timeout_seconds = timeout_seconds
        self._opener = build_opener(HTTPSHandler(context=ssl.create_default_context()),
                                    _RejectRedirects())

    def request(self, endpoint: str, *, data: bytes | None = None,
                headers: dict[str, str] | None = None, limit: int = MAX_JSON_BYTES) -> dict:
        try:
            req = Request(endpoint, data=data, headers=headers or {},
                          method="POST" if data is not None else "GET")
            with self._opener.open(req, timeout=self.timeout_seconds) as response:
                if response.status != 200:
                    raise ProviderUnavailable("identity provider returned non-success")
                if not response.headers.get("Content-Type", "").lower().split(";")[0].strip() == "application/json":
                    raise ProviderUnavailable("identity provider response is not JSON")
                raw = response.read(limit + 1)
            if len(raw) > limit:
                raise ProviderUnavailable("identity provider response too large")
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ProviderUnavailable("identity provider response must be an object")
            return result
        except (HTTPError, URLError, TimeoutError, OSError, UnicodeError,
                json.JSONDecodeError, ValueError) as error:
            raise ProviderUnavailable("identity provider unavailable or invalid response") from None


class VerifiedProviderClient:
    def __init__(self, settings: PinnedProvider, http: ProviderHTTP | None = None):
        self.settings = settings
        self.http = http or ProviderHTTP()

    def fetch_trusted_jwks(self) -> dict:
        keys = self.http.request(self.settings.jwks_uri)
        candidate = OIDCConfig(
            self.settings.issuer, self.settings.client_id, keys,
            require_mfa=self.settings.require_mfa,
            accepted_acr=self.settings.accepted_acr,
        )
        # Avoid trusting key references, key use and algorithms from tokens.
        kids: set[str] = set()
        for item in candidate.jwks["keys"]:
            if (not isinstance(item, dict) or item.get("kty") != "RSA"
                    or item.get("alg", "RS256") != "RS256"
                    or item.get("use", "sig") != "sig"
                    or not isinstance(item.get("kid"), str)
                    or not SAFE_SEGMENT.fullmatch(item["kid"])
                    or item["kid"] in kids):
                raise ProviderUnavailable("unusable or ambiguous provider signing keys")
            try:
                RSAAlgorithm.from_jwk(item)
            except (ValueError, TypeError, KeyError):
                raise ProviderUnavailable("invalid provider RSA public signing key") from None
            kids.add(item["kid"])
        if len(kids) > 32:
            raise ProviderUnavailable("provider published too many signing keys")
        return keys

    def verify_discovery(self) -> None:
        # Only an explicitly configured endpoint is fetched; metadata cannot
        # introduce an untrusted authorization, JWKS, or token URL.
        metadata_url = self.settings.issuer + "/.well-known/openid-configuration"
        _https_endpoint(metadata_url)
        document = self.http.request(metadata_url)
        for key, expected in (
            ("issuer", self.settings.issuer),
            ("authorization_endpoint", self.settings.authorization_endpoint),
            ("token_endpoint", self.settings.token_endpoint),
            ("jwks_uri", self.settings.jwks_uri),
        ):
            if document.get(key) != expected:
                raise ProviderUnavailable("provider metadata differs from pinned configuration")
        if (not isinstance(document.get("response_types_supported"), list)
                or "code" not in document["response_types_supported"]):
            raise ProviderUnavailable("provider does not support authorization code")
        if (not isinstance(document.get("id_token_signing_alg_values_supported"), list)
                or "RS256" not in document["id_token_signing_alg_values_supported"]):
            raise ProviderUnavailable("provider RS256 support missing")
        if (not isinstance(document.get("code_challenge_methods_supported"), list)
                or "S256" not in document["code_challenge_methods_supported"]):
            raise ProviderUnavailable("provider PKCE S256 support missing")

    def exchange_code(self, code: str, verifier: str, redirect_uri: str,
                      client_id: str) -> str:
        if (redirect_uri != self.settings.redirect_uri
                or client_id != self.settings.client_id
                or not 16 <= len(code) <= 4096
                or not 43 <= len(verifier) <= 128):
            raise ProviderUnavailable("invalid authorization code exchange")
        # A client secret is only sent to the operator-pinned HTTPS token URL.
        credentials = base64.b64encode(
            (quote_plus(client_id) + ":" + quote_plus(self.settings.client_secret)).encode("ascii")
        ).decode("ascii")
        form = urlencode({
            "grant_type":"authorization_code",
            "code":code,
            "redirect_uri":redirect_uri,
            "code_verifier":verifier,
        }).encode("ascii")
        response = self.http.request(
            self.settings.token_endpoint, data=form,
            headers={"Authorization":"Basic " + credentials,
                     "Content-Type":"application/x-www-form-urlencoded"},
            limit=MAX_TOKEN_BYTES,
        )
        token = response.get("id_token")
        if not isinstance(token, str) or not 20 <= len(token) <= 16384:
            raise ProviderUnavailable("provider did not return valid ID token")
        return token

    def create_login_flow(self, store: LoginStore, *, session_lifetime_seconds: int = 3600,
                          verify_metadata: bool = True) -> OIDCLoginFlow:
        if verify_metadata:
            self.verify_discovery()
        config = OIDCConfig(
            issuer=self.settings.issuer, client_id=self.settings.client_id,
            jwks=self.fetch_trusted_jwks(),
            require_mfa=self.settings.require_mfa,
            accepted_acr=self.settings.accepted_acr,
        )
        return OIDCLoginFlow(
            OIDCLoginSettings(
                authorization_endpoint=self.settings.authorization_endpoint,
                redirect_uri=self.settings.redirect_uri, oidc=config,
                session_lifetime_seconds=session_lifetime_seconds,
            ),
            store,
            self.exchange_code,
            refresh_jwks=self.fetch_trusted_jwks,
        )
