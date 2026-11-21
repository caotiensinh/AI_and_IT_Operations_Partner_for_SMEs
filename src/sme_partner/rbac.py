"""Fail-closed resource-scoped RBAC; not a replacement for OIDC or DB RLS."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID
from .tenant_context import AuthorizedTenantContext, TenantAccessDenied


class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    OPERATOR = "operator"
    VIEWER = "viewer"


class Action(str, Enum):
    READ = "resource.read"
    UPDATE = "resource.update"
    ACKNOWLEDGE = "alert.acknowledge"
    APPROVE = "workflow.approve"
    MANAGE_USERS = "users.manage"
    CONFIGURE = "tenant.configure"


class ScopeType(str, Enum):
    TENANT = "tenant"
    SITE = "site"
    DEPARTMENT = "department"


PERMISSIONS: dict[Role, frozenset[Action]] = {
    Role.OWNER: frozenset(Action),
    Role.ADMIN: frozenset(Action),
    Role.MANAGER: frozenset({Action.READ, Action.UPDATE, Action.ACKNOWLEDGE, Action.APPROVE}),
    Role.OPERATOR: frozenset({Action.READ, Action.ACKNOWLEDGE}),
    Role.VIEWER: frozenset({Action.READ}),
}


@dataclass(frozen=True, slots=True)
class Assignment:
    tenant_id: UUID
    identity_id: UUID
    role: Role
    scope_type: ScopeType
    scope_id: UUID | None


@dataclass(frozen=True, slots=True)
class Resource:
    tenant_id: UUID
    site_id: UUID
    department_id: UUID | None = None
    # Ancestor IDs are server-resolved from a trusted tenant-constrained DB query.
    department_ancestors: frozenset[UUID] = frozenset()


class PermissionDenied(PermissionError):
    pass


def require_permission(
    context: AuthorizedTenantContext,
    assignments: tuple[Assignment, ...],
    action: Action,
    resource: Resource,
) -> None:
    """Deny unknown actions, identities, tenants, roles, or missing scope.

    Assignments and resource ownership must come from trusted tenant-scoped
    database reads, NOT browser input or self-reported JWT role claims.
    """
    if not isinstance(context, AuthorizedTenantContext) or not isinstance(action, Action):
        raise PermissionDenied("invalid authorization context")
    if resource.tenant_id != context.tenant_id:
        raise TenantAccessDenied("cross-tenant resource")
    for grant in assignments:
        if grant.tenant_id != context.tenant_id or grant.identity_id != context.identity_id:
            continue
        if not isinstance(grant.role, Role) or not isinstance(grant.scope_type, ScopeType):
            continue
        if action not in PERMISSIONS[grant.role]:
            continue
        if grant.scope_type == ScopeType.TENANT and grant.scope_id is None:
            return
        if grant.scope_type == ScopeType.SITE and grant.scope_id == resource.site_id:
            return
        if (grant.scope_type == ScopeType.DEPARTMENT
                and resource.department_id is not None
                and grant.scope_id in (resource.department_ancestors | {resource.department_id})):
            return
    raise PermissionDenied("role or resource scope denied")
