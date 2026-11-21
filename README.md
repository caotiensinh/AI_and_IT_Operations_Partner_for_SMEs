# AI & IT Operations Partner for SMEs

**Mission:** Help small and medium enterprises reduce operating costs, improve productivity, and control risks using practical, secure and measurable automation.

**Architecture:** Business & Experience (L1) → Domain & Application Services (L2) → Platform & Infrastructure (L3).

**Status:** Architecture baseline and Spec Kit proposal. No production application is implemented yet. All capabilities below are proposed and must pass acceptance tests before being described as operational.

## Principles

1. One platform, four bounded domains: Office AI, IT Operations, Vision AI and IoT Operations.
2. Python and Rust for core processing; TypeScript/React for cross-device presentation.
3. Every customer is a security tenant: server-side tenant authorization, PostgreSQL Row-Level Security, isolated object namespaces, tenant-scoped jobs and audit trails.
4. Users have explicit tenant memberships and scoped roles; a global operator does not automatically gain access to customer data.
5. Desktop first for complex operations, tablet for field work, smartphone for quick actions and alerts.
6. Cloud, on-premises and hybrid edge supported through deployment profiles; no multi-cloud promise without testing.
7. No production-data export, model training or third-party AI processing without explicit authorization.
8. Prefer a modular monolith and independently scalable workers over premature microservices.

## Documentation

- [Product vision](.specify/memory/constitution.md)
- [Spec Kit: platform specification](specs/001-platform-foundation/spec.md)
- [Technical plan and architecture decisions](specs/001-platform-foundation/plan.md)
- [Implementation tasks](specs/001-platform-foundation/tasks.md)
- [Architecture overview](docs/architecture/overview.md)
- [Security, tenant isolation and roles](docs/architecture/security.md)
- [UI and responsive UX specification](docs/architecture/ux.md)
- [Data architecture](docs/architecture/data.md)
- [Initial architecture decision records](docs/adr/0001-foundation.md)
- [Business research: four Japanese SME cases](docs/research/2026-11-chubu-sme-four-case-study.md)
- [Business requirements traceability matrix](docs/research/requirements-traceability-matrix.md)
- [Spec Kit 003: SME business needs and discovery](specs/003-sme-business-needs/spec.md)
- [Spec Kit 003: implementation and research tasks](specs/003-sme-business-needs/tasks.md)

## Proposed stack

- Python 3.12+ / FastAPI, Pydantic, SQLAlchemy 2, Alembic
- Rust stable / Tokio for edge agents, high-throughput connectors and security-sensitive ingestion
- React + TypeScript + Vite; accessible responsive PWA
- PostgreSQL as system of record; object storage compatible with S3 for documents/video; Redis/Valkey for ephemeral cache and job delivery
- OIDC identity provider, MFA, OpenAPI contracts, OpenTelemetry
- Docker Compose for development and early production; dedicated on-prem profiles as required

Version constraints and licensing must be reviewed and locked in manifests before implementation.

## Lifecycle

DISCOVER → SPECIFY → DESIGN → IMPLEMENT → TEST → VERIFY → DEPLOY → OPERATE.

Do not merge tenant-sensitive functionality without negative cross-tenant tests, authorization tests and migration/rollback evidence.
