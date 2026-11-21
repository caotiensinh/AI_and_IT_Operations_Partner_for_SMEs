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

    @app.get("/v1/tenants/{tenant_id}/research-cases/{case_id}/requirements")
    def list_case_requirements(tenant_id: UUID, case_id: UUID,
                               authorization: str | None = Header(default=None)):
        digest = _digest(authorization)
        with connect() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE sme_app")
                session = conn.execute(
                    "SELECT sme.resolve_session(%s,%s)", (digest,tenant_id),
                ).fetchone()
                if session is None or session[0] is None:
                    raise HTTPException(403, "tenant access denied")
                conn.execute("SELECT set_config('sme.tenant_id',%s,true)", (str(tenant_id),))
                case = conn.execute(
                    "SELECT site_id FROM sme.discovery_cases WHERE tenant_id=%s AND id=%s",
                    (tenant_id,case_id),
                ).fetchone()
                if case is None:
                    raise HTTPException(404, "case not found")
                grants = conn.execute(
                    "SELECT role,scope_type,site_id,department_id FROM sme.role_assignments "
                    "WHERE tenant_id=%s AND identity_id=%s",
                    (tenant_id, session[0]),
                ).fetchall()
                assignments = tuple(
                    Assignment(tenant_id=tenant_id,identity_id=session[0],
                               role=Role(role),scope_type=ScopeType(scope_type),
                               scope_id=site if scope_type=="site" else
                                   department if scope_type=="department" else None)
                    for role,scope_type,site,department in grants
                )
                try:
                    require_permission(
                        AuthorizedTenantContext(session[0],tenant_id),assignments,
                        Action.READ, Resource(tenant_id,case[0]),
                    )
                except (PermissionDenied,TenantAccessDenied):
                    # Do not expose existence of a case across unauthorized sites.
                    raise HTTPException(404, "case not found") from None
                records = conn.execute(
                    "SELECT r.id,r.statement,r.classification,r.approval_state,"
                    "s.document_label,s.source_page "
                    "FROM sme.discovery_requirements r "
                    "LEFT JOIN sme.discovery_sources s ON "
                    "s.tenant_id=r.tenant_id AND s.case_id=r.case_id AND s.id=r.source_id "
                    "WHERE r.tenant_id=%s AND r.case_id=%s "
                    "ORDER BY r.id LIMIT 101", (tenant_id,case_id),
                ).fetchall()
                return {"tenant_id":str(tenant_id),"case_id":str(case_id),
                        "limit":101,"requirements":[
                            {"id":str(uid),"statement":statement,
                             "classification":classification,"approval_state":approval,
                             "source":(
                                 {"document_label":document,"page":page}
                                 if document is not None else None)}
                            for uid,statement,classification,approval,document,page in records
                        ]}

    return app
