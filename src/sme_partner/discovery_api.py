"""Read-only API for a discovery research case, using server-resolved session and RBAC.

Pilot only: no customer intake/consent or migration import service. Database
connection must use trusted server configuration; never connect as production
table owner. Do not expose raw source documents through this API.
"""
from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import psycopg
from fastapi import FastAPI, Header, HTTPException

from .rbac import Action, Assignment, PermissionDenied, Resource, Role, ScopeType, require_permission
from .session_api import _digest
from .tenant_context import AuthorizedTenantContext, TenantAccessDenied


def create_discovery_app(connect: Callable[[], psycopg.Connection]) -> FastAPI:
    app = FastAPI(title="SME Research Discovery Read API", version="0.1.0")

    def _visible_cases(conn, tenant_id: UUID, identity_id: UUID):
        grants = conn.execute(
            "SELECT role,scope_type,site_id,department_id "
            "FROM sme.role_assignments WHERE tenant_id=%s AND identity_id=%s",
            (tenant_id, identity_id),
        ).fetchall()
        assignments = tuple(
            Assignment(
                tenant_id=tenant_id,
                identity_id=identity_id,
                role=Role(role), scope_type=ScopeType(scope_type),
                scope_id=site if scope_type == "site" else
                    department if scope_type == "department" else None,
            )
            for role, scope_type, site, department in grants
        )
        rows = conn.execute(
            "SELECT id,site_id,label,company_code,status FROM sme.discovery_cases "
            "WHERE tenant_id=%s ORDER BY label,id LIMIT 101", (tenant_id,),
        ).fetchall()
        context = AuthorizedTenantContext(identity_id, tenant_id)
        visible = []
        for case_id, site_id, label, company_code, status in rows:
            try:
                require_permission(context, assignments, Action.READ,
                                   Resource(tenant_id, site_id))
            except (PermissionDenied, TenantAccessDenied):
                continue
            visible.append({
                "id": str(case_id), "site_id": str(site_id),
                "label": label, "company_code": company_code, "status": status,
            })
        return visible

    @app.get("/v1/tenants/{tenant_id}/research-cases")
    def list_research_cases(tenant_id: UUID, authorization: str | None = Header(default=None)):
        digest = _digest(authorization)
        with connect() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE sme_app")
                session = conn.execute(
                    "SELECT sme.resolve_session(%s,%s)", (digest, tenant_id),
                ).fetchone()
                if session is None or session[0] is None:
                    raise HTTPException(403, "tenant access denied")
                conn.execute("SELECT set_config('sme.tenant_id',%s,true)", (str(tenant_id),))
                cases = _visible_cases(conn, tenant_id, session[0])
                # Bounded pilot endpoint; no fake cursor/pagination guarantees.
                return {"tenant_id": str(tenant_id), "cases": cases, "limit": 101}

    return app
