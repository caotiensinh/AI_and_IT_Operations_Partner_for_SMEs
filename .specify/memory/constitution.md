# Project Constitution — v1.0

## Mission
Deliver an enterprise-grade, affordable, multi-tenant operations platform for SMEs, covering Office AI, IT Operations, Vision AI and IoT Operations. Prioritize measurable business results over novelty.

## Non-negotiable engineering rules
1. **Tenant isolation first.** Every tenant-owned record, object, cache entry, background task, event and log context has an enforceable tenant boundary. A client-provided tenant identifier is never authority.
2. **Least privilege.** Authentication and authorization are different. Enforce tenant membership, role, scope and resource permissions on the server. Deny by default.
3. **Security by design.** MFA, TLS, encrypted storage, managed secrets, key rotation, audit logs, secure sessions, dependency scans and incident response. No silent access by platform operators.
4. **Evidence-based delivery.** A feature is done only with code, positive/negative tests, persisted documentation, CI proof and reproducible deployment steps.
5. **Portable and resilient.** Support Linux/Windows development, browsers on desktop/tablet/mobile; Rust edge agents may run on supported Linux/Windows platforms. Do not claim mobile native agents.
6. **Simple user experience.** Role-based workspaces, low-click actions, accessible keyboard and touch flows, no desktop screen blindly shrunk to mobile.
7. **Pragmatic architecture.** Start modular monolith with bounded contexts and replaceable adapters; use microservices only for measured reasons.
8. **Data ownership.** Tenant data belongs to the tenant under contract. Explicit export, retention and deletion policy. No model training without consent.
9. **Operational clarity.** Define SLOs, backup, restores, incident runbooks, scope boundaries and supported deployment profiles.
10. **Change safety.** Migrations and deployments are reversible or have documented recovery; changes require review and tests.

## Governance
Architecture Decision Records are mandatory for changes to authentication, isolation, persistence, public API, deployment and core language choices. Exceptions require explicit threat analysis and test evidence.
