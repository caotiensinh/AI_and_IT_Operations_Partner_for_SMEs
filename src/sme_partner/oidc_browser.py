"""Browser OIDC entry/callback adapter over the existing verified login flow.

This module never exposes an ID token or first-party session token to
JavaScript or redirect URLs. A later BFF layer must verify the HttpOnly session
cookie and enforce CSRF protections before it can call write APIs.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, Response

from .oidc_flow import LoginRejected, OIDCLoginFlow

# __Host- requires Secure, Path=/, and no Domain attribute.
_BINDING_COOKIE = "__Host-sme_oidc_binding"
_SESSION_COOKIE = "__Host-sme_session"
_PRIVATE_HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache"}
_ALLOWED_PATH = re.compile(r"^/[A-Za-z0-9/_-]*$")


@dataclass(frozen=True)
class BrowserLoginSettings:
    """Fixed local redirect after identity verification; not user-supplied."""

    post_login_path: str = "/"

    def __post_init__(self) -> None:
        if not _ALLOWED_PATH.fullmatch(self.post_login_path) or self.post_login_path.startswith("//"):
            raise ValueError("post_login_path must be an absolute local path")


def create_oidc_browser_app(
    flow: OIDCLoginFlow, *, settings: BrowserLoginSettings = BrowserLoginSettings()
) -> FastAPI:
    """Bind to a trusted HTTPS origin behind a hardened reverse proxy.

    Caller provides a *pinned* OIDC provider's token exchange implementation.
    This adapter intentionally has no local-token-minting/test-only endpoint.
    """
    app = FastAPI(title="SME Partner OIDC Browser Bridge", version="0.1.0")

    @app.get("/auth/oidc/start")
    def start_login() -> Response:
        start = flow.start()
        result = RedirectResponse(start.authorization_url, status_code=302)
        result.set_cookie(
            _BINDING_COOKIE, start.browser_binding, secure=True, httponly=True,
            samesite="lax", path="/", max_age=300,
        )
        result.headers.update(_PRIVATE_HEADERS)
        return result

    @app.get("/auth/oidc/callback")
    def finish_login(request: Request) -> Response:
        # Fail closed: a provider error is not proof of authentication.
        state = request.query_params.get("state")
        code = request.query_params.get("code")
        error = request.query_params.get("error")
        binding = request.cookies.get(_BINDING_COOKIE)
        if error is not None or not state or not code or not binding:
            result: Response = Response("Login could not be completed", status_code=401)
        else:
            try:
                token = flow.complete(
                    state=state, code=code, browser_binding=binding
                )
                result = RedirectResponse(settings.post_login_path, status_code=303)
                result.set_cookie(
                    _SESSION_COOKIE, token, secure=True, httponly=True,
                    samesite="lax", path="/",
                    max_age=flow.settings.session_lifetime_seconds,
                )
            except LoginRejected:
                result = Response("Login could not be completed", status_code=401)
            except Exception:
                # No provider details, tokens, or exception data in browser responses.
                result = Response("Login could not be completed", status_code=401)
        # The state-binding browser cookie must never survive a callback attempt.
        result.delete_cookie(_BINDING_COOKIE, path="/", secure=True, httponly=True, samesite="lax")
        result.headers.update(_PRIVATE_HEADERS)
        return result

    return app
