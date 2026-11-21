"""Tenant-safe integration boundary for SME partner services.

No upstream code or data is imported; source projects remain independent.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID


class Domain(str, Enum):
    OFFICE = "office_ai"
    IT = "it_operations"
    VISION = "vision_ai"
    IOT = "iot_operations"


class IntegrationError(Exception):
    """Base integration policy failure."""


class TenantBoundaryError(IntegrationError):
    """Missing or mismatched authorized tenant."""


class CapabilityDenied(IntegrationError):
    """Disabled integration/capability or unauthorized operation."""


@dataclass(frozen=True, slots=True)
class Principal:
    subject_id: UUID
    tenant_id: UUID
    allowed_capabilities: frozenset[str]


@dataclass(frozen=True, slots=True)
class AdapterManifest:
    adapter_id: str
    source_repository: str
    domain: Domain
    capabilities: frozenset[str]
    enabled: bool = False


@dataclass(frozen=True, slots=True)
class AuthorizedInvocation:
    tenant_id: UUID
    principal_id: UUID
    adapter_id: str
    capability: str
    resource_id: UUID


class AdapterRegistry:
    """Allowlist registry; authorization precedes any adapter invocation.

    This kernel intentionally has no execute method; future adapters must accept
    AuthorizedInvocation only and re-check scoped resource ownership at storage.
    """

    def __init__(self, manifests: tuple[AdapterManifest, ...] = ()) -> None:
        if len({m.adapter_id for m in manifests}) != len(manifests):
            raise ValueError("duplicate adapter_id")
        self._manifests = {m.adapter_id: m for m in manifests}

    def authorize(
        self,
        *,
        principal: Principal,
        requested_tenant_id: UUID,
        adapter_id: str,
        capability: str,
        resource_id: UUID,
    ) -> AuthorizedInvocation:
        if principal.tenant_id != requested_tenant_id:
            raise TenantBoundaryError("tenant context denied")
        manifest = self._manifests.get(adapter_id)
        if manifest is None or not manifest.enabled:
            raise CapabilityDenied("integration disabled")
        if capability not in manifest.capabilities or capability not in principal.allowed_capabilities:
            raise CapabilityDenied("capability denied")
        return AuthorizedInvocation(
            tenant_id=requested_tenant_id,
            principal_id=principal.subject_id,
            adapter_id=adapter_id,
            capability=capability,
            resource_id=resource_id,
        )


CANDIDATE_ADAPTERS = (
    AdapterManifest("billumi-ocr", "caotiensinh/Billumi", Domain.OFFICE, frozenset({"document.extract"})),
    AdapterManifest("office-workflow", "caotiensinh/workflow_office_deadline", Domain.OFFICE, frozenset({"workflow.evaluate"})),
    AdapterManifest("asahi-monitor", "caotiensinh/ubuntu_asahi_server", Domain.IT, frozenset({"asset.metrics.read"})),
    AdapterManifest("reverse-rea-vision", "caotiensinh/Reverse_rea", Domain.VISION, frozenset({"vision.inspect"})),
    AdapterManifest("golf-camera", "caotiensinh/golf_ball_detect", Domain.VISION, frozenset({"camera.capture"})),
    AdapterManifest("gpio-edge", "caotiensinh/GPIO-raspberrypi", Domain.IOT, frozenset({"device.state.read"})),
    AdapterManifest("audio-transcribe", "caotiensinh/LAN_Audio_AI", Domain.OFFICE, frozenset({"meeting.transcribe"})),
    AdapterManifest("browser-automation", "caotiensinh/AI_Web_MCP", Domain.OFFICE, frozenset({"browser.read"})),
)
