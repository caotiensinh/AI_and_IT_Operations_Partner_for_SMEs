# ADR-0001 — Foundation Architecture Decisions

**Status:** Proposed (requires review before coding).

## Decision
- Three-layer business/domain/platform architecture with bounded contexts.
- Python FastAPI modular monolith as authoritative business backend.
- Rust Tokio for high-throughput ingestion, local agents and integrations requiring stable low-overhead execution.
- React/TypeScript responsive PWA for desktop, tablet and mobile; native mobile apps deferred.
- PostgreSQL as system of record; database RLS enforced with explicit membership/scoped authorization.
- S3-compatible object storage for binary and large media; optional Redis/Valkey for ephemeral work.
- OIDC + MFA; tenant admin policies and audited, time-bound support escalation.
- Start with Docker Compose on Linux, Windows development supported; multiple deployment profiles with tested boundaries.

## Alternatives and rationale
- Microservices now: rejected due to complexity/operations cost without measured load.
- Separate full apps per domain: rejected due to duplicated tenant identity and permission logic.
- SQLite as shared production DB: rejected due to multi-tenant concurrency and row policy requirements.
- Rust-only API: deferred, because Python domain integration and AI libraries shorten pilot development; Rust remains core agent/worker language.
- Native iOS/Android from day one: rejected; PWA first, revisit hardware/offline limitations after field pilots.
- Kubernetes mandatory: rejected; add when scaling or isolation requirements justify it.

## Risks / revisitation
- Shared-schema isolation requires security expertise and continuous negative tests; offer database-per-tenant when warranted.
- PWA device APIs vary by browser/OS; test real camera/scanning/offline needs.
- OIDC external dependency requires recovery plan.
- Redis/Valkey licensing/version choices require review before pinning.
- Data residency, Japanese APPI compliance and contracts require legal/security review before customer use.
