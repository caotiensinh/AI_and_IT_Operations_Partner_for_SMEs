"""Tenant selection after trusted OIDC/session identity resolution.

The caller must be trusted server middleware; this is not OIDC implementation.
"""
from dataclasses import dataclass
from uuid import UUID

class TenantAccessDenied(PermissionError):
    pass

@dataclass(frozen=True, slots=True)
class VerifiedIdentity:
    identity_id: UUID
    issuer: str

@dataclass(frozen=True, slots=True)
class ActiveMembership:
    identity_id: UUID
    tenant_id: UUID
    active: bool

@dataclass(frozen=True, slots=True)
class AuthorizedTenantContext:
    identity_id: UUID
    tenant_id: UUID

def authorize_tenant(identity: VerifiedIdentity, tenant_id: UUID,
                     memberships: tuple[ActiveMembership, ...]) -> AuthorizedTenantContext:
    """Deny unless an active membership matches identity and tenant exactly."""
    if not identity.issuer or not isinstance(tenant_id, UUID):
        raise TenantAccessDenied("invalid session or tenant")
    if not any(m.active and m.identity_id == identity.identity_id and m.tenant_id == tenant_id
               for m in memberships):
        raise TenantAccessDenied("tenant membership denied")
    return AuthorizedTenantContext(identity_id=identity.identity_id, tenant_id=tenant_id)
