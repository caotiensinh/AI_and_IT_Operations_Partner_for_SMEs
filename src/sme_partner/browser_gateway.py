"""OIDC browser transport: secure cookies, callback, and CSRF-bound logout.

Mount behind an HTTPS reverse proxy with a fixed, validated public origin.
The flow/store and revoke callback are injected to separate the auth DB role
from the runtime DB role. A browser cookie is NEVER an OAuth ID token.
"""
from __future__ import annotations

from collections.abc import Callable
import hashlib
import hmac
from urllib.parse import urlsplit

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from .oidc_flow import LoginRejected, OIDCLoginFlow

SESSION_COOKIE = "__Host-sme_session"
BIND_COOKIE = "__Host-sme_oidc_bind"
CSRF_HEADER = "X-CSRF-Token"


def _session_csrf(token: str, key: bytes) -> str:
    return hmac.new(key, token.encode("ascii"), hashlib.sha256).hexdigest()


def install_browser_gateway(
    app: FastAPI,
    flow: OIDCLoginFlow,
    *,
    public_origin: str,
    csrf_key: bytes,
    revoke_session: Callable[[str], None],
    session_active: Callable[[str], bool],
) -> None:
    """Install browser routes; no login, default key or secrets are auto-created."""
    parts = urlsplit(public_origin)
    if (parts.scheme != "https" or not parts.hostname or parts.username
            or parts.password or parts.query or parts.fragment
            or parts.path not in ("", "/")):
        raise ValueError("public_origin must be a fixed HTTPS origin")
    if len(csrf_key) < 32:
        raise ValueError("CSRF signing key must contain >=32 random bytes")
    origin = public_origin.rstrip("/")

    @app.get("/auth/start")
    def start_login():
        login = flow.start()
        response = RedirectResponse(login.authorization_url, status_code=302)
        response.set_cookie(BIND_COOKIE, login.browser_binding, max_age=300,
                            secure=True, httponly=True, samesite="lax", path="/")
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/auth/callback")
    def login_callback(request: Request, code: str = "", state: str = ""):
        binding = request.cookies.get(BIND_COOKIE)
        try:
            if not binding:
                raise LoginRejected("login failed")
            token = flow.complete(state=state, browser_binding=binding, code=code)
        except LoginRejected:
            response = JSONResponse({"detail": "login failed"}, status_code=401)
            response.delete_cookie(BIND_COOKIE, path="/", secure=True, httponly=True, samesite="lax")
            response.headers["Cache-Control"] = "no-store"
            return response
        response = RedirectResponse(origin + "/app", status_code=303)
        response.delete_cookie(BIND_COOKIE, path="/", secure=True, httponly=True, samesite="lax")
        response.set_cookie(SESSION_COOKIE, token, max_age=flow.settings.session_lifetime_seconds,
                            secure=True, httponly=True, samesite="lax", path="/")
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/auth/csrf")
    def browser_csrf(request: Request):
        session = request.cookies.get(SESSION_COOKIE)
        if not session or len(session) != 43 or not session_active(session):
            raise HTTPException(401, "authentication required")
        response = JSONResponse({"csrf_token": _session_csrf(session, csrf_key)})
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.post("/auth/logout", status_code=204)
    def browser_logout(request: Request, origin_header: str | None = Header(None, alias="Origin"),
                       csrf_header: str | None = Header(None, alias=CSRF_HEADER)):
        session = request.cookies.get(SESSION_COOKIE)
        if origin_header != origin or not session or len(session) != 43 or not session_active(session):
            raise HTTPException(403, "request denied")
        expected = _session_csrf(session, csrf_key)
        if not isinstance(csrf_header, str) or not hmac.compare_digest(csrf_header, expected):
            raise HTTPException(403, "request denied")
        revoke_session(session)
        response = JSONResponse(status_code=204, content=None)
        response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax")
        response.headers["Cache-Control"] = "no-store"
        return response
