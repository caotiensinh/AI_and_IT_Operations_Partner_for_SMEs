"""Pinned HTTPS OIDC token exchange adapter.

Expected endpoint and redirect URI are operator configuration, not client input.
No token contents or HTTP response body should be logged by this adapter.
"""
from __future__ import annotations

from urllib.parse import urlsplit
import httpx

from .oidc import AuthenticationDenied


class OIDCTokenExchange:
    def __init__(self, token_endpoint: str, *, timeout_seconds: float = 8.0,
                 client: httpx.Client | None = None) -> None:
        parsed = urlsplit(token_endpoint)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.fragment or parsed.query):
            raise ValueError("token endpoint must be a trusted fixed HTTPS URL")
        if not 0.5 <= timeout_seconds <= 30.0:
            raise ValueError("invalid token exchange timeout")
        self.endpoint = token_endpoint
        self.timeout = timeout_seconds
        self.client = client

    def __call__(self, code: str, verifier: str, redirect_uri: str, client_id: str) -> str:
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
        }
        try:
            if self.client is not None:
                response = self.client.post(self.endpoint, data=payload,
                                            follow_redirects=False, timeout=self.timeout)
            else:
                with httpx.Client(follow_redirects=False, timeout=self.timeout, trust_env=False) as client:
                    response = client.post(self.endpoint, data=payload)
            if response.status_code != 200 or len(response.content) > 65536:
                raise AuthenticationDenied("token exchange failed")
            body = response.json()
            token = body.get("id_token") if isinstance(body, dict) else None
            if not isinstance(token, str) or len(token) > 16384 or token.count(".") != 2:
                raise AuthenticationDenied("token exchange failed")
            return token
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise AuthenticationDenied("token exchange failed") from None
