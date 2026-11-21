# Implementation Backlog — Spec 001

Acceptance evidence must be linked in future PRs. All tasks currently OPEN unless a merged implementation proves otherwise.

| ID | Task | Dependencies | Acceptance |
|---|---|---|---|
| T001 | Toolchain, layout and pinned manifests | None | Python/Rust/TS lint and tests run in CI on clean checkout |
| T002 | PostgreSQL schema + migrations | T001 | Up/down migrations and constraints tested |
| T003 | Tenant context and RLS policies | T002 | Cross-tenant SQL tests fail closed, including pooled connections |
| T004 | OIDC and session handling | T001 | Valid/expired/revoked sessions and MFA tested |
| T005 | Membership, RBAC and org hierarchy | T003,T004 | Unauthorized lateral access denied |
| T006 | Audit/outbox schema and delivery | T003 | Retries preserve idempotency, privilege changes audited |
| T007 | Object storage policy and signed URL broker | T003,T005 | Cross-tenant URLs denied and expiry enforced |
| T008 | Responsive shell and design tokens | T004 | Desktop/tablet/mobile E2E navigation tests |
| T009 | Tenant workspace dashboard, inbox | T005,T008 | Role-specific task completion in 3 clicks where feasible |
| T010 | Python OA-01 document processing PoC | T006,T007 | Human-reviewed extracted fields, duplicate protection |
| T011 | IT-01 inventory + monitoring adapter | T006 | Scoped device telemetry and operational alert |
| T012 | Rust agent skeleton with scoped identity | T001,T005 | Wrong tenant/site device rejected |
| T013 | Recovery, backup and restore drills | T002,T007 | RPO/RTO evidence on test deployment |
| T014 | Security/performance baseline | T008,T009 | WCAG review, p95 benchmark, threat model |
| T015 | Pilot with first tenant | T010,T011,T013,T014 | Contract-specific outcome measurement and sign-off |

## Milestones
M0: architecture agreed and documented (this PR).
M1: tenant security kernel implemented and proven.
M2: responsive shell and role-aware workspace.
M3: OA-01 + IT-01 pilot deployment.
M4: verified production operations.
