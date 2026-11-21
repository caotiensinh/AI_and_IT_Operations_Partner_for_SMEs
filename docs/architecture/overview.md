# Architecture Overview — C4-style Context and Containers

## Context
The customer owns a tenant with one or more sites, departments, users and registered devices. The platform operator manages subscriptions, upgrades and service health, but does not automatically access customer business data.

## L1 — Business & Experience
- Desktop: dense workbench, accessible navigation, data tables, bulk actions and audit drill-down.
- Tablet: field checklist, status cards, camera/photo capture (browser permissions), landscape/portrait support.
- Smartphone: notifications, approvals, search, quick actions, on-site scanning.
- Tenant switch is explicit and clearly visible; theme, locale and permitted modules follow tenant context.

## L2 — Domain Services
Domain contracts: tenant-scoped commands, queries, domain events and adapters. No inter-domain direct table reads.
- Office AI: document ingestion, OCR, validation, approvals, export integration.
- IT Ops: inventory, checks, incidents, support workflows.
- Vision AI: cameras, inference configuration, review and evidence.
- IoT Ops: devices, gateways, telemetry, rules and alerts.
Shared: approvals, notifications, scheduler, job queue, AI provider policy.

## L3 — Platform & Infrastructure
OIDC identity, Postgres/RLS, object storage, transactional outbox, background workers, optional Redis/Valkey, observability, backup and recovery.

```mermaid
flowchart TB
  subgraph L1["L1 · Experience"]
    D[Desktop] --> P[Responsive React PWA]
    T[Tablet] --> P
    M[Smartphone] --> P
  end
  P --> G[HTTPS Reverse Proxy / API]
  subgraph L2["L2 · Domain and Application"]
    G --> A[Python FastAPI Modular Monolith]
    A --> O[Office AI]
    A --> I[IT Operations]
    A --> V[Vision AI]
    A --> Q[IoT Operations]
    A --> W[Workflow and Approval]
  end
  subgraph L3["L3 · Platform"]
    A --> ID[OIDC / Authorization]
    A --> DB[(PostgreSQL + RLS)]
    A --> OBJ[(Tenant-scoped Object Storage)]
    A --> OUT[Transactional Outbox / Jobs]
    OUT --> PW[Python AI Workers]
    OUT --> RW[Rust Workers / Edge]
    A --> AUD[Audit & Telemetry]
  end
```

## Deployment profiles
- **Shared SaaS:** shared compute/DB cluster, enforced logical isolation, per-tenant object namespaces and credentials, no guaranteed physical isolation.
- **Dedicated:** per-tenant DB and storage credentials/instance, separate environment where requested.
- **Hybrid:** edge processing stays on site; only explicitly allowed events/media leave the site, with retry and offline buffering.

## Architecture quality gates
Reliability, confidentiality, auditability, ease of use, upgradeability and low cost must be measured, not assumed.
