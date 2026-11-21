# Spec 001 — Platform Foundation (Draft for Implementation)

## Product scope
A configurable multi-tenant enterprise platform with a unified workspace and four bounded operational domains:
- **L1 Business & Experience:** Tenant onboarding, organization tree, workspace, dashboards, action inbox, reports, approvals and responsive UI.
- **L2 Application services:** Office AI, IT Operations, Vision AI, IoT Operations; workflow and notification infrastructure; activity/event history.
- **L3 Platform:** Identity, authorization, storage, jobs, audit, monitoring, backup and deployment.

## Personas
- Platform owner: manages subscriptions, platform health and tenant provisioning **without default access to customer payloads**.
- Platform support: metadata-only diagnostics; time-limited, audited customer-approved support elevation.
- Tenant owner: owns organization and controls tenant policies and billing.
- Tenant admin: manages memberships and configured modules, except ownership transfer.
- Department manager: views/approves scoped department resources.
- Operator: executes allowed operational tasks.
- Viewer/auditor: read-only within explicitly assigned scopes.
- Device/agent: non-human principal restricted by tenant/site/device scopes.

## Requirements
FR-001: Tenant onboarding creates an immutable tenant UUID, workspace and an initial owner membership; repeat calls must be idempotent.
FR-002: Identity is global, but permissions are derived from tenant memberships and scope assignments; membership may span tenants with explicit per-tenant switching.
FR-003: Tenant user hierarchy supports organization → sites → departments → groups and assigned resources; inherited permissions are limited to defined descendants.
FR-004: Every API resource access enforces tenant and resource scopes server-side. A tenant ID in path or header does not grant access.
FR-005: Four domains are independently enabled using tenant entitlements. Disabled domains do not expose data/actions.
FR-006: An action inbox supports assigned tasks, approvals, alerts and audit-friendly histories.
FR-007: Dashboard widgets vary by role and screen class while preserving consistent backend semantics.
FR-008: Documents, image/video objects, sensor time series and audit events have tenant-specific storage and lifecycle policies.
FR-009: Async jobs capture tenant ID, actor/service principal, idempotency key, correlation ID, authorized resource scope, retries, and dead-letter handling.
FR-010: Support English/Japanese/Vietnamese via localization, Japanese as first launch locale, no hard-coded text in domain services.
FR-011: Allow tenant export and deletion with documented retention/legal hold and auditable confirmation; never immediately delete required compliance logs.
FR-012: Feature flags, integration adapters and OIDC provider settings are tenant-scoped.
FR-013: Edge gateway cannot access any tenant except its bound identity, uses mTLS where available and receives only signed/configured jobs.
FR-014: Provide documented shared SaaS, dedicated on-prem and hybrid edge deployment profiles, each with explicit data-flow boundaries.
FR-015: For AI processing, per-tenant policy specifies permitted providers, retention, approval requirements and redaction rules.

## Non-functional requirements (initial targets; validate with pilot hardware)
NFR-001: First usable action on desktop <=3 clicks from dashboard for top-five role tasks, measured in usability tests.
NFR-002: Core API p95 latency <300ms at 50 concurrent users on reference test environment (excluding AI inference/large downloads).
NFR-003: Accessible navigation, WCAG 2.2 AA target, >=44px touch targets where practicable, screen-reader labels, keyboard support.
NFR-004: TLS in transit; encryption at rest for DB and object store; secrets outside source; MFA required for privileged humans.
NFR-005: Define RPO <=24h and RTO <=8h for initial single-region offering, verified by real restore drills; stricter contractual tiers are separate.
NFR-006: All tenant-owned SQL tables use RLS plus scoped repository methods; negative isolation tests across tenants mandatory.
NFR-007: Audit privileged actions, exports, identity changes and support elevation; redact secrets and sensitive content.
NFR-008: Desktop/tablet/mobile widths: 1440px, 1024px, 768px, 390px and 320px baseline screenshots and interaction tests.

## Out of scope for the first release
- Native iOS/Android applications.
- Full ERP replacement.
- Video storage inside PostgreSQL.
- Unattended autonomous actions that alter customer production systems without explicit approval.
- Arbitrary cross-tenant analytics on raw customer payloads.
- Guaranteed 24/7 human response without staffing.

## Acceptance examples
AT-001: Two tenants A/B each create identical resource names; every tenant access returns only its records, including list, direct ID lookup, search, export, job result and object download.
AT-002: A user with memberships in A and B must explicitly select context; a forged tenant header/path is rejected.
AT-003: Platform support cannot read customer documents absent time-limited, approved and audited access.
AT-004: Department operator cannot approve owner-level changes or access another department.
AT-005: Uploaded objects cannot be retrieved via guessed key, URL or stale pre-signed link after policy changes.
AT-006: Mobile UI performs acknowledge-alert and assigned-task completion without horizontal scrolling.
AT-007: A simulated worker retry does not duplicate a customer business operation.
AT-008: Restore test proves tenant metadata/object references consistent with retention policy.
