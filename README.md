# AI & IT Operations Partner for SMEs

**Mission:** Help small and medium enterprises reduce operating costs, improve productivity, and control risks using practical, secure and measurable automation.

**Architecture:** Business & Experience (L1) → Domain & Application Services (L2) → Platform & Infrastructure (L3).

**Status:** Architecture and Spec Kit baseline. The Business Discovery/API, tenant security, Japanese Workspace and OIDC integration are implemented and validated **on stacked open feature PRs**, not yet merged into `main` or deployed to customers. Passing synthetic CI is not production readiness. Other modules below remain proposed until independently accepted.

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
- [Reusable SME interview and discovery worksheet](docs/research/sme-discovery-interview-template.md)
- [Spec Kit 003: SME business needs and discovery](specs/003-sme-business-needs/spec.md)
- [Spec Kit 003: implementation and research tasks](specs/003-sme-business-needs/tasks.md)
- [Staging integration gate and safe release procedure](docs/architecture/discovery-staging-integration-gate.md)
- [Pinned PR integration evidence snapshot](specs/003-sme-business-needs/integration-chain.json)
- [Enterprise OIDC deployment preflight](docs/architecture/oidc-deployment-preflight.md)

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
