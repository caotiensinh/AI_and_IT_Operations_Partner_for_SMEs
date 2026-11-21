"""Pilot API for discovery cases, using server-resolved session and DB-enforced RBAC.

Pilot only: guarded case creation; no general customer intake/consent or import. Database
connection must use trusted server configuration; never connect as production
table owner. Do not expose raw source documents through this API.
"""
from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import psycopg
from fastapi import FastAPI, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field
from typing import Literal

from .rbac import Action, Assignment, PERMISSIONS, PermissionDenied, Resource, Role, ScopeType, require_permission
from .session_api import _digest
from .tenant_context import AuthorizedTenantContext, TenantAccessDenied



class ReviewRequirement(BaseModel):
    expected_version: int = Field(ge=0)
    decision: Literal["confirmed","rejected"]
    rationale: str = Field(min_length=8,max_length=2000)


class CreateRequirement(BaseModel):
    requirement_id: UUID
    statement: str = Field(min_length=1,max_length=4000)
    classification: Literal["explicit","inferred","unverified"]
    source_id: UUID | None = None


class CreateSourceMetadata(BaseModel):
    source_id: UUID
    document_label: str = Field(min_length=1,max_length=200)
    page: int = Field(ge=1)


class CreateResearchCase(BaseModel):
    site_id: UUID
    label: str = Field(min_length=1, max_length=200)
    company_code: Literal["B", "J", "L", "R", "OTHER"]



def create_discovery_app(connect: Callable[[], psycopg.Connection]) -> FastAPI:
    app = FastAPI(title="SME Research Discovery Read API", version="0.1.0")

    def _visible_cases(conn, tenant_id: UUID, identity_id: UUID,
                       limit: int, after: UUID | None):
        """Filter authorized site scopes *before* SQL pagination."""
        grants = conn.execute(
            "SELECT role,scope_type,site_id,department_id "
            "FROM sme.role_assignments WHERE tenant_id=%s AND identity_id=%s",
            (tenant_id,identity_id),
        ).fetchall()
        full_tenant = False
        sites: set[UUID] = set()
        for role, scope_type, site_id, department_id in grants:
            if Action.READ not in PERMISSIONS[Role(role)]:
                continue
            if scope_type == "tenant":
                full_tenant = True
            elif scope_type == "site" and site_id is not None:
                sites.add(site_id)
        if not full_tenant and not sites:
            return [], None
        query = (
            "SELECT id,site_id,label,company_code,status FROM sme.discovery_cases "
            "WHERE tenant_id=%s AND (%s::uuid IS NULL OR id>%s::uuid) "
            "AND (%s OR site_id=ANY(%s::uuid[])) ORDER BY id LIMIT %s"
        )
        rows = conn.execute(query, (tenant_id,after,after,full_tenant,
                                   list(sites),limit+1)).fetchall()
        page = rows[:limit]
        return ([{"id":str(cid),"site_id":str(site_id),
                  "label":label,"company_code":company_code,"status":status}
                 for cid,site_id,label,company_code,status in page],
                str(page[-1][0]) if len(rows)>limit else None)

    @app.get("/v1/tenants/{tenant_id}/research-cases")
    def list_research_cases(tenant_id: UUID, limit: int = Query(default=50,ge=1,le=100),
                            after: UUID | None = Query(default=None),
                            authorization: str | None = Header(default=None)):
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
                cases, next_cursor = _visible_cases(conn, tenant_id, session[0], limit, after)
                return {"tenant_id": str(tenant_id), "cases": cases,
                        "limit": limit, "next_cursor": next_cursor}

    @app.get("/v1/tenants/{tenant_id}/research-cases/{case_id}/requirements")
    def list_case_requirements(tenant_id: UUID, case_id: UUID,
                               limit: int = Query(default=50,ge=1,le=100),
                               after: UUID | None = Query(default=None),
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
                    "AND (%s::uuid IS NULL OR r.id>%s::uuid) "
                    "ORDER BY r.id LIMIT %s", (tenant_id,case_id,after,after,limit+1),
                ).fetchall()
                page = records[:limit]
                return {"tenant_id":str(tenant_id),"case_id":str(case_id),
                        "limit":limit,
                        "next_cursor":str(page[-1][0]) if len(records)>limit else None,
                        "requirements":[
                            {"id":str(uid),"statement":statement,
                             "classification":classification,"approval_state":approval,
                             "source":(
                                 {"document_label":document,"page":page}
                                 if document is not None else None)}
                            for uid,statement,classification,approval,document,page in page
                        ]}

    @app.post("/v1/tenants/{tenant_id}/research-cases", status_code=201)
    def create_research_case(tenant_id: UUID, request: CreateResearchCase,
                             response: Response,
                             idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                             authorization: str | None = Header(default=None)):
        digest = _digest(authorization)
        if (not idempotency_key or len(idempotency_key) not in range(16,129)
                or not all(c.isascii() and (c.isalnum() or c in "_-")
                           for c in idempotency_key)):
            raise HTTPException(422, "Idempotency-Key must be 16-128 ASCII URL-safe characters")
        if not request.label.strip():
            raise HTTPException(422, "nonempty case label required")
        with connect() as conn:
            with conn.transaction():
                # sme_app has NO direct INSERT on research tables or audit events.
                conn.execute("SET LOCAL ROLE sme_app")
                result = conn.execute(
                    "SELECT result_case_id,is_replay,is_conflict "
                    "FROM sme.create_discovery_case_once(%s,%s,%s,%s,%s,%s)",
                    (digest,tenant_id,request.site_id,request.label,
                     request.company_code,idempotency_key),
                ).fetchone()
                if not result or result[0] is None:
                    raise HTTPException(403, "case creation denied")
                if result[2]:
                    raise HTTPException(409, "idempotency key reused with different payload")
                response.status_code = 200 if result[1] else 201
                return {"tenant_id":str(tenant_id),"case_id":str(result[0]),
                        "status":"research","replayed":result[1]}


    @app.post("/v1/tenants/{tenant_id}/research-cases/{case_id}/sources", status_code=201)
    def create_case_source(tenant_id: UUID, case_id: UUID,
                           request: CreateSourceMetadata, response: Response,
                           authorization: str | None = Header(default=None)):
        digest=_digest(authorization)
        if not request.document_label.strip():
            raise HTTPException(422,"source label required")
        with connect() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE sme_app")
                result=conn.execute(
                    "SELECT result_source_id,is_replay,is_conflict "
                    "FROM sme.create_discovery_source_once(%s,%s,%s,%s,%s,%s)",
                    (digest,tenant_id,case_id,request.source_id,
                     request.document_label,request.page),
                ).fetchone()
                if not result or result[0] is None:
                    raise HTTPException(403,"source creation denied")
                if result[2]:
                    raise HTTPException(409,"source id reused for different metadata")
                response.status_code=200 if result[1] else 201
                return {"tenant_id":str(tenant_id),"case_id":str(case_id),
                        "source_id":str(result[0]),"replayed":result[1]}


    @app.post("/v1/tenants/{tenant_id}/research-cases/{case_id}/requirements",status_code=201)
    def create_case_requirement(tenant_id: UUID,case_id: UUID,
                                request: CreateRequirement,response: Response,
                                authorization: str | None = Header(default=None)):
        digest=_digest(authorization)
        if not request.statement.strip() or (
                request.classification=="explicit" and request.source_id is None):
            raise HTTPException(422,"explicit statements require a source")
        with connect() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE sme_app")
                result=conn.execute(
                    "SELECT result_requirement_id,is_replay,is_conflict "
                    "FROM sme.create_discovery_requirement_once(%s,%s,%s,%s,%s,%s,%s)",
                    (digest,tenant_id,case_id,request.requirement_id,
                     request.statement,request.classification,request.source_id),
                ).fetchone()
                if not result or result[0] is None:
                    raise HTTPException(403,"requirement creation denied")
                if result[2]:
                    raise HTTPException(409,"requirement ID reused for different statement")
                response.status_code=200 if result[1] else 201
                return {"tenant_id":str(tenant_id),"case_id":str(case_id),
                        "requirement_id":str(result[0]),"approval_state":"proposed",
                        "replayed":result[1]}


    @app.post("/v1/tenants/{tenant_id}/research-cases/{case_id}/requirements/{requirement_id}/review")
    def review_case_requirement(tenant_id: UUID,case_id: UUID,requirement_id: UUID,
                                request: ReviewRequirement,
                                authorization: str | None = Header(default=None)):
        digest=_digest(authorization)
        if not request.rationale.strip() or len(request.rationale.strip())<8:
            raise HTTPException(422,"review rationale must contain at least 8 characters")
        with connect() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE sme_app")
                result=conn.execute(
                    "SELECT result_status,result_version,result_state "
                    "FROM sme.review_discovery_requirement(%s,%s,%s,%s,%s,%s,%s)",
                    (digest,tenant_id,case_id,requirement_id,
                     request.expected_version,request.decision,request.rationale),
                ).fetchone()
                if not result:
                    raise HTTPException(403,"review denied")
                status,version,state=result
                if status=="denied":
                    raise HTTPException(403,"review denied")
                if status=="conflict":
                    raise HTTPException(409,"review version mismatch")
                if status=="invalid":
                    raise HTTPException(422,"invalid review transition or evidence")
                if status not in ("updated","unchanged"):
                    raise HTTPException(500,"unexpected review status")
                return {"tenant_id":str(tenant_id),"case_id":str(case_id),
                        "requirement_id":str(requirement_id),
                        "approval_state":state,"review_version":version,
                        "updated":status=="updated"}


    return app
