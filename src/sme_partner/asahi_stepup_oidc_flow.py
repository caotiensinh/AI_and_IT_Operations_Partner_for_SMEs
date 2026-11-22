"""Isolated OIDC step-up orchestration; intentionally no public HTTP endpoints.

Only a trusted HTTPS BFF should call this service with a server-resolved
session, tenant, action, browser binding, and opaque destination references.
No DB roles are provisioned for production here.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Callable, Protocol
from urllib.parse import urlencode, urlsplit
from uuid import UUID

from .asahi_stepup_verifier import verify_fresh_stepup
from .oidc import AuthenticationDenied
from .oidc_flow import OIDCLoginSettings, _challenge, _digest, _secret

_SECRET_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")
_REF_RE = re.compile(r"^[A-Za-z0-9_./-]{1,128}$")


class StepupRejected(PermissionError):
    """Return only this generic failure across the future HTTP trust boundary."""


@dataclass(frozen=True, slots=True)
class StepupStart:
    authorization_url: str
    state: str
    browser_binding: str


@dataclass(frozen=True, slots=True)
class StepupAction:
    tenant_id: UUID
    action: str
    channel: str | None = None
    destination_ref: str | None = None
    secret_ref: str | None = None

    def __post_init__(self) -> None:
        if self.tenant_id.int == 0:
            raise ValueError("invalid tenant")
        if self.action == "revoke":
            if any(v is not None for v in (self.channel,self.destination_ref,self.secret_ref)):
                raise ValueError("revoke cannot carry delivery references")
        elif self.action == "approve":
            if self.channel not in ("email","webhook"):
                raise ValueError("unsupported channel")
            for ref in (self.destination_ref,self.secret_ref):
                if (not isinstance(ref,str) or not _REF_RE.fullmatch(ref)
                        or ref.startswith("/") or ".." in ref.split("/")):
                    raise ValueError("unsafe destination reference")
        else:
            raise ValueError("invalid approval action")


class StepupStore(Protocol):
    def begin(self, *, state_digest: bytes, browser_digest: bytes,
              session_digest: bytes, action: StepupAction,
              verifier: str, nonce: str) -> bool: ...
    def consume(self, *, state_digest: bytes, browser_digest: bytes,
                session_digest: bytes, action: StepupAction) -> tuple[str,str] | None: ...
    def identity(self, session_digest: bytes, tenant: UUID) -> tuple[str,str] | None: ...
    def issue(self, *, session_digest: bytes, action: StepupAction,
              lifetime: int) -> UUID | None: ...


class AsahiStepupOIDCFlow:
    def __init__(self, settings: OIDCLoginSettings, store: StepupStore,
                 exchange_code: Callable[[str,str,str,str],str],
                 *, proof_lifetime: int = 60):
        if type(proof_lifetime) is not int or not 15 <= proof_lifetime <= 120:
            raise ValueError("invalid proof lifetime")
        self.settings = settings
        self.store = store
        self.exchange_code = exchange_code
        self.proof_lifetime = proof_lifetime

    def start(self, *, session_digest: bytes, action: StepupAction) -> StepupStart:
        if not isinstance(session_digest,bytes) or len(session_digest)!=32:
            raise StepupRejected("step-up denied")
        state,browser,nonce=_secret(),_secret(),_secret()
        verifier=_secret(48)
        if not self.store.begin(
            state_digest=_digest(state),browser_digest=_digest(browser),
            session_digest=session_digest,action=action,verifier=verifier,nonce=nonce
        ):
            raise StepupRejected("step-up denied")
        params={
            "response_type":"code",
            "client_id":self.settings.oidc.client_id,
            "redirect_uri":self.settings.redirect_uri,
            "scope":"openid",
            "state":state,
            "nonce":nonce,
            "code_challenge":_challenge(verifier),
            "code_challenge_method":"S256",
            # Ask for a fresh authentication, but verify actual signed auth_time.
            "prompt":"login",
            "max_age":"0",
        }
        endpoint=self.settings.authorization_endpoint
        connector="&" if urlsplit(endpoint).query else "?"
        return StepupStart(endpoint+connector+urlencode(params),state,browser)

    def complete(self, *, session_digest: bytes, action: StepupAction,
                 state: str, browser_binding: str, code: str) -> UUID:
        if (not isinstance(session_digest,bytes) or len(session_digest)!=32
            or not isinstance(state,str) or not _SECRET_RE.fullmatch(state)
            or not isinstance(browser_binding,str) or not _SECRET_RE.fullmatch(browser_binding)
            or not isinstance(code,str) or not 16 <= len(code) <= 4096):
            raise StepupRejected("step-up denied")
        pending=self.store.consume(
            state_digest=_digest(state),browser_digest=_digest(browser_binding),
            session_digest=session_digest,action=action
        )
        if pending is None:
            raise StepupRejected("step-up denied")
        verifier,nonce=pending
        try:
            identity=self.store.identity(session_digest,action.tenant_id)
            if identity is None:
                raise StepupRejected("step-up denied")
            id_token=self.exchange_code(
                code,verifier,self.settings.redirect_uri,self.settings.oidc.client_id
            )
            verify_fresh_stepup(
                id_token,self.settings.oidc,
                expected_issuer=identity[0],expected_subject=identity[1],
                expected_nonce=nonce
            )
            proof=self.store.issue(
                session_digest=session_digest,action=action,lifetime=self.proof_lifetime
            )
            if proof is None:
                raise StepupRejected("step-up denied")
            return proof
        except (AuthenticationDenied, ValueError, TypeError, StepupRejected):
            # The challenge has already been consumed and cannot be retried.
            raise StepupRejected("step-up denied") from None


class PostgresStepupStore:
    """All functions execute only with an independently provisioned sme_stepup role.

    The supplied connection MUST be a narrowly privileged trusted issuer.
    Never use the migration owner or generic SME application connection in prod.
    """
    def __init__(self, connect: Callable):
        self.connect=connect

    def begin(self, *, state_digest: bytes, browser_digest: bytes,
              session_digest: bytes, action: StepupAction,
              verifier: str, nonce: str) -> bool:
        with self.connect() as conn:
            with conn.transaction():
                return bool(conn.execute(
                    "SELECT sme.begin_asahi_stepup_challenge("
                    "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (state_digest,browser_digest,session_digest,action.tenant_id,
                     action.action,action.channel,action.destination_ref,
                     action.secret_ref,verifier,nonce)
                ).fetchone()[0])

    def consume(self, *, state_digest: bytes, browser_digest: bytes,
                session_digest: bytes, action: StepupAction) -> tuple[str,str] | None:
        with self.connect() as conn:
            with conn.transaction():
                row=conn.execute(
                    "SELECT code_verifier,expected_nonce FROM "
                    "sme.consume_asahi_stepup_challenge(%s,%s,%s,%s,%s,%s,%s,%s)",
                    (state_digest,browser_digest,session_digest,action.tenant_id,
                     action.action,action.channel,action.destination_ref,action.secret_ref)
                ).fetchone()
                return (row[0],row[1]) if row else None

    def identity(self, session_digest: bytes, tenant: UUID) -> tuple[str,str] | None:
        with self.connect() as conn:
            with conn.transaction():
                row=conn.execute(
                    "SELECT issuer,subject FROM sme.resolve_asahi_stepup_identity(%s,%s)",
                    (session_digest,tenant)
                ).fetchone()
                return (row[0],row[1]) if row else None

    def issue(self, *, session_digest: bytes, action: StepupAction,
              lifetime: int) -> UUID | None:
        with self.connect() as conn:
            with conn.transaction():
                row=conn.execute(
                    "SELECT sme.issue_asahi_stepup(%s,%s,%s,%s,%s,%s,%s)",
                    (session_digest,action.tenant_id,action.action,action.channel,
                     action.destination_ref,action.secret_ref,lifetime)
                ).fetchone()
                return row[0] if row else None
