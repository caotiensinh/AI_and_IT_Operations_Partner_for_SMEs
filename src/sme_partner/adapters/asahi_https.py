"""Read-only, enrollment-configured HTTPS polling adapter for ASAHI agents.

This module performs NO device enrollment, no database writes and no remote
control. The upstream ASAHI agent exposes GET /api/agent/status with bearer
authorization and HTTPS; the server must configure endpoint, trust roots and
binding using administrator-verified enrollment records, never browser input.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re
import ssl
from urllib.parse import urlsplit

import httpx

from .asahi import DeviceBinding, MetricRejected, NormalizedTelemetry, normalize_asahi_snapshot


class AgentPollRejected(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TrustedAgentEndpoint:
    url: str
    bearer_token: str
    certificate_authority_file: str
    binding: DeviceBinding

    def __post_init__(self) -> None:
        uri = urlsplit(self.url)
        if (uri.scheme != "https" or not uri.hostname or uri.username or uri.password
                or uri.path != "/api/agent/status" or uri.query or uri.fragment):
            raise ValueError("Asahi endpoint must be a fixed HTTPS status URL")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{32,256}",self.bearer_token):
            raise ValueError("invalid agent token format")
        if not isinstance(self.certificate_authority_file,str) or not self.certificate_authority_file:
            raise ValueError("agent certificate trust anchor is required")
        if not isinstance(self.binding,DeviceBinding):
            raise ValueError("trusted device binding is required")


class AsahiHTTPSPoller:
    def __init__(self, endpoint: TrustedAgentEndpoint, *,
                 client: httpx.Client | None = None, timeout_seconds: float = 5.0,
                 max_response_bytes: int = 65536) -> None:
        if not 0.5 <= timeout_seconds <= 20:
            raise ValueError("invalid timeout")
        if not 1024 <= max_response_bytes <= 262144:
            raise ValueError("invalid maximum response")
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        # A supplied client is for controlled integration tests only. Production
        # always builds its own TLS-verified, no-proxy, no-redirect HTTP client.
        self.client = client

    def poll(self, observed_at: datetime) -> NormalizedTelemetry:
        own_client = self.client is None
        client = self.client
        if own_client:
            try:
                trust = ssl.create_default_context(cafile=self.endpoint.certificate_authority_file)
                client = httpx.Client(verify=trust,follow_redirects=False,
                                      trust_env=False,timeout=self.timeout_seconds)
            except (OSError,ssl.SSLError,ValueError):
                raise AgentPollRejected("agent trust configuration invalid") from None
        try:
            with client.stream(
                "GET",self.endpoint.url,
                headers={"Authorization":"Bearer "+self.endpoint.bearer_token,
                         "Accept":"application/json"},
                timeout=self.timeout_seconds,
                follow_redirects=False,
            ) as response:
                if response.status_code != 200:
                    raise AgentPollRejected("agent request rejected")
                content_type=response.headers.get("Content-Type","").split(";")[0].strip().lower()
                if content_type!="application/json":
                    raise AgentPollRejected("invalid telemetry content type")
                body=bytearray()
                for chunk in response.iter_bytes(chunk_size=8192):
                    body.extend(chunk)
                    if len(body)>self.max_response_bytes:
                        raise AgentPollRejected("telemetry response too large")
            payload=json.loads(body)
            return normalize_asahi_snapshot(
                payload=payload,binding=self.endpoint.binding,observed_at=observed_at,
            )
        except (httpx.HTTPError,ValueError,TypeError,UnicodeError,MetricRejected) as exc:
            raise AgentPollRejected("agent telemetry rejected") from None
        finally:
            if own_client and client is not None:
                client.close()
