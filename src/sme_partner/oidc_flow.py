"""Server-side OIDC Authorization Code + PKCE transaction, with DB-backed single-use state.

The trusted token exchange callback must POST to a pinned provider token endpoint
with code_verifier, exact redirect_uri and client_id. Never accept a token endpoint
or redirect URI from the inbound request. This module intentionally contains no UI
and never logs credential values.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import hmac
import secrets
from typing import Callable, Protocol
from urllib.parse import urlencode, urlsplit

from .oidc import AuthenticationDenied, OIDCConfig, verify_id_token


def _secret(n: int = 32) -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(n)).rstrip(b"=").decode("ascii")


def _digest(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("ascii")).digest()


def _challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(_digest(verifier)).rstrip(b"=").decode("ascii")


class LoginRejected(PermissionError):
    pass


class LoginStore(Protocol):
    def begin(self, state_digest: bytes, browser_digest: bytes, verifier: str, nonce: str) -> None: ...
    def consume(self, state_digest: bytes, browser_digest: bytes) -> tuple[str, str] | None: ...
    def issue(self, issuer: str, subject: str, token_digest: bytes, ttl_seconds: int) -> bool: ...


@dataclass(frozen=True)
class LoginStart:
    authorization_url: str
    state: str
    browser_binding: str


@dataclass(frozen=True)
class OIDCLoginSettings:
    authorization_endpoint: str
    redirect_uri: str
    oidc: OIDCConfig
    session_lifetime_seconds: int = 3600

    def __post_init__(self) -> None:
        for endpoint in (self.authorization_endpoint, self.redirect_uri):
            url = urlsplit(endpoint)
            if url.scheme != "https" or not url.hostname or url.username or url.password or url.fragment:
                raise ValueError("OIDC endpoints must be fixed HTTPS URLs")
        if not 60 <= self.session_lifetime_seconds <= 28800:
            raise ValueError("session lifetime outside allowed bounds")


class OIDCLoginFlow:
    def __init__(
        self,
        settings: OIDCLoginSettings,
        store: LoginStore,
        exchange_code: Callable[[str, str, str, str], str],
    ):
        self.settings = settings
        self.store = store
        self.exchange_code = exchange_code

    def start(self) -> LoginStart:
        state, binding, nonce = _secret(), _secret(), _secret()
        verifier = _secret(48)
        self.store.begin(_digest(state), _digest(binding), verifier, nonce)
        params = {
            "response_type": "code",
            "client_id": self.settings.oidc.client_id,
            "redirect_uri": self.settings.redirect_uri,
            "scope": "openid",
            "state": state,
            "nonce": nonce,
            "code_challenge": _challenge(verifier),
            "code_challenge_method": "S256",
        }
        connector = "&" if urlsplit(self.settings.authorization_endpoint).query else "?"
        return LoginStart(self.settings.authorization_endpoint + connector + urlencode(params), state, binding)

    def complete(self, *, state: str, browser_binding: str, code: str) -> str:
        if not all(isinstance(s, str) and 16 <= len(s) <= 4096 for s in (state, browser_binding, code)):
            raise LoginRejected("login failed")
        # State and browser cookie must be high entropy, correct length and URL-safe.
        for value in (state, browser_binding):
            if len(value) != 43 or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in value):
                raise LoginRejected("login failed")
        pending = self.store.consume(_digest(state), _digest(browser_binding))
        if pending is None:
            raise LoginRejected("login failed")
        verifier, nonce = pending
        try:
            id_token = self.exchange_code(
                code, verifier, self.settings.redirect_uri, self.settings.oidc.client_id
            )
            subject = verify_id_token(id_token, self.settings.oidc, expected_nonce=nonce)
        except (AuthenticationDenied, ValueError, TypeError):
            raise LoginRejected("login failed") from None
        # A new credential is issued only after signature, issuer, audience and nonce
        # validation and an active internal identity/membership match in the DB.
        session_token = _secret()
        if not self.store.issue(
            subject.issuer, subject.subject, _digest(session_token),
            self.settings.session_lifetime_seconds
        ):
            raise LoginRejected("login failed")
        return session_token


class PostgresLoginStore:
    """Separate auth DB role. Caller provides its own least-privilege connection."""

    def __init__(self, connect: Callable):
        self.connect = connect

    def begin(self, state_digest: bytes, browser_digest: bytes, verifier: str, nonce: str) -> None:
        with self.connect() as conn:
            with conn.transaction():
                conn.execute("SELECT sme.begin_oidc_login(%s,%s,%s,%s)",
                             (state_digest, browser_digest, verifier, nonce))

    def consume(self, state_digest: bytes, browser_digest: bytes) -> tuple[str, str] | None:
        with self.connect() as conn:
            with conn.transaction():
                row = conn.execute("SELECT code_verifier,expected_nonce FROM sme.consume_oidc_login(%s,%s)",
                                   (state_digest, browser_digest)).fetchone()
                return (row[0], row[1]) if row else None

    def issue(self, issuer: str, subject: str, token_digest: bytes, ttl_seconds: int) -> bool:
        with self.connect() as conn:
            with conn.transaction():
                return bool(conn.execute(
                    "SELECT sme.issue_oidc_session(%s,%s,%s,%s)",
                    (issuer, subject, token_digest, ttl_seconds)
                ).fetchone()[0])
