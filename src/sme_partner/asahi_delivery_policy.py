"""Fail-closed tenant routing policy for future Asahi alert delivery.

No HTTP addresses, provider credentials, network I/O or secret resolution live
here. Callers must authenticate the dispatcher and resolve approved references
in a separate secret-manager boundary before sending any notification.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
from types import MappingProxyType
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ApprovedDestination:
    tenant_id: UUID
    channel: str
    destination_ref: str
    secret_ref: str
    enabled: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.tenant_id, UUID) or self.tenant_id.int == 0:
            raise ValueError("invalid tenant")
        if self.channel not in ("email", "webhook"):
            raise ValueError("unsupported channel")
        for ref in (self.destination_ref, self.secret_ref):
            if not isinstance(ref, str) or not 1 <= len(ref) <= 128:
                raise ValueError("invalid opaque reference")
            if not all(char.isascii() and (char.isalnum() or char in "_-./") for char in ref):
                raise ValueError("invalid opaque reference")
            if ref.startswith("/") or ".." in ref.split("/") or "://" in ref:
                raise ValueError("invalid opaque reference")
        if type(self.enabled) is not bool:
            raise ValueError("invalid enabled flag")


@dataclass(frozen=True, slots=True)
class DeliveryAuthorization:
    tenant_id: UUID
    event_id: int
    channel: str
    destination_ref: str
    secret_ref: str
    idempotency_key: str


class TenantDeliveryPolicy:
    """Immutable tenant-scoped allowlist; defaults to denial."""

    def __init__(self, destinations: Mapping[UUID, ApprovedDestination]):
        if not isinstance(destinations, Mapping):
            raise ValueError("destination map required")
        entries = {}
        for tenant_id, destination in destinations.items():
            if not isinstance(tenant_id, UUID) or not isinstance(destination, ApprovedDestination):
                raise ValueError("invalid destination mapping")
            if tenant_id != destination.tenant_id:
                raise ValueError("cross-tenant destination mapping")
            entries[tenant_id] = destination
        self._destinations = MappingProxyType(entries)

    def authorize(self, *, tenant_id: UUID, event_id: int) -> DeliveryAuthorization:
        if not isinstance(tenant_id, UUID) or tenant_id.int == 0:
            raise ValueError("invalid tenant")
        if type(event_id) is not int or not 1 <= event_id <= 9223372036854775807:
            raise ValueError("invalid event")
        destination = self._destinations.get(tenant_id)
        if destination is None or not destination.enabled:
            raise PermissionError("tenant delivery not approved")
        return DeliveryAuthorization(
            tenant_id=tenant_id,
            event_id=event_id,
            channel=destination.channel,
            destination_ref=destination.destination_ref,
            secret_ref=destination.secret_ref,
            idempotency_key=str(event_id),
        )
