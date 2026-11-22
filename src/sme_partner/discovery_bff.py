"""Same-origin cookie BFF for Discovery API; no session token delivered to JavaScript.

Use with a trusted HTTPS reverse proxy. An explicit trusted-origin setting,
CSRF binding and a separated app-role connection are mandatory.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Callable
from urllib.parse import urlsplit

import psycopg
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response

from .discovery_api import create_discovery_app
from .session_api import TOKEN_RE

_SESSION_COOKIE = "__Host-sme_session"
_CSRF_HEADER = "x-csrf-token"
_NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache", "Vary": "Cookie"}
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _trusted_origin(origin: str) -> str:
    parsed = urlsplit(origin)
    if (parsed.scheme != "https" or not parsed.hostname
            or parsed.username or parsed.password or parsed.path not in ("", "/")
            or parsed.query or parsed.fragment):
        raise ValueError("BFF requires a pinned HTTPS origin (scheme + authority only)")
    return origin.rstrip("/")


def create_cookie_discovery_app(
    connect: Callable[[], psycopg.Connection], *, csrf_secret: bytes,
    trusted_origin: str,
):
    """Create a cookie-only BFF. The legacy bearer-only API is unchanged elsewhere."""
    origin = _trusted_origin(trusted_origin)
    if not isinstance(csrf_secret, bytes) or len(csrf_secret) < 32:
        raise ValueError("CSRF HMAC key must be at least 32 unpredictable bytes")
    app = create_discovery_app(connect)

    def session_token(request: Request) -> str | None:
        token = request.cookies.get(_SESSION_COOKIE)
        return token if token and TOKEN_RE.fullmatch(token) else None

    def csrf_token(token: str) -> str:
        return hmac.new(csrf_secret, ("discovery-bff-v1:" + token).encode("ascii"),
                        hashlib.sha256).hexdigest()

    @app.middleware("http")
    async def cookie_boundary(request: Request, call_next):
        path = request.url.path
        protected = path.startswith("/v1/tenants/") or path.startswith("/auth/session/")
        if not protected:
            # Do not accidentally publish unprotected endpoints on this BFF.
            return JSONResponse({"detail": "not found"}, status_code=404,
                                headers=_NO_STORE)
        token = session_token(request)
        if token is None:
            return JSONResponse({"detail": "authentication required"},status_code=401,
                                headers=_NO_STORE)
        # Do not let caller supply an alternative bearer to bypass cookie CSRF.
        if request.headers.get("authorization") is not None:
            return JSONResponse({"detail": "bearer not accepted"},status_code=400,
                                headers=_NO_STORE)
        if request.method not in _SAFE_METHODS:
            source = request.headers.get("origin")
            header = request.headers.get(_CSRF_HEADER)
            if (source != origin or not header
                    or not hmac.compare_digest(header, csrf_token(token))):
                return JSONResponse({"detail": "CSRF verification failed"},
                                    status_code=403,headers=_NO_STORE)
        if path.startswith("/v1/tenants/"):
            # In-memory ASGI header injection; never exposed to browser.
            scope = request.scope
            scope["headers"] = [
                (k,v) for k,v in scope["headers"]
                if k.lower() != b"authorization"
            ] + [(b"authorization", ("Bearer " + token).encode("ascii"))]
        response = await call_next(request)
        response.headers.update(_NO_STORE)
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/auth/session/tenants")
    def visible_tenants(request: Request):
        token = session_token(request)
        if token is None:
            raise HTTPException(401, "authentication required")
        digest = hashlib.sha256(token.encode("ascii")).digest()
        with connect() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE sme_app")
                rows = conn.execute("SELECT tenant_id,tenant_label "
                                    "FROM sme.list_session_tenants(%s)",(digest,)).fetchall()
        if not rows:
            raise HTTPException(401,"authentication required")
        if len(rows)>100:
            raise HTTPException(403,"tenant selection limit exceeded")
        return {"tenants":[{"id":str(uid),"label":label} for uid,label in rows],
                "csrf_token":csrf_token(token)}

    @app.post("/auth/session/logout",status_code=204)
    def logout(request: Request):
        token = session_token(request)
        if token is None:
            raise HTTPException(401,"authentication required")
        digest=hashlib.sha256(token.encode("ascii")).digest()
        with connect() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE sme_app")
                conn.execute("SELECT sme.revoke_session(%s)",(digest,))
        response=Response(status_code=204)
        response.delete_cookie(_SESSION_COOKIE,path="/",secure=True,
                               httponly=True,samesite="lax")
        return response

    return app
