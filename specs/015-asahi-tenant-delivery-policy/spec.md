# Spec 015 — Tenant-approved delivery routing boundary

## Objective
Introduce an **offline, fail-closed routing decision** before any future outbound Asahi alert notifier. Existing claim/ack persistence from Spec 013 is unchanged. No external notifications are sent.

## Architecture
- L1 customer/operator: tenant owner approves notification channel and destination in a future authenticated UI.
- L2 dispatch: trusted dispatcher supplies **server-derived** tenant UUID and durable event UUID (never user/browser-selected tenant); policy returns only an authorized *opaque reference* and stable event UUID idempotency key.
- L3 secret boundary: a future approved resolver maps opaque references to configured endpoints and credentials. Enforce tenant ownership, HTTPS verification, egress allowlisting, SSRF defenses and audit *there*, not in browser inputs.

## Acceptance
- [x] Missing, disabled and cross-tenant destinations fail closed.
- [x] Immutable snapshot of tenant policy; external dictionary changes cannot silently alter approval.
- [x] Validate tenant/event UUIDs and restricted opaque reference syntax.
- [x] Return stable event ID as provider idempotency key; never claim exactly-once delivery.
- [x] Tests cover deny, allow, cross-tenant, invalid values, and stable identity.
- [ ] Store approval in tenant-scoped PostgreSQL with explicit authorized approver and revocation audit.
- [ ] Secret manager integration and strict outbound endpoint validation.
- [ ] Real provider adapter with timeout, retry, idempotency, provider response logging and lease-aware ack.
- [ ] Security review and hardware E2E on approved Asahi device.

## Non-goals
This is a *policy contract*, not an email sender, webhook client, tenant self-service UI, production approval workflow or secret manager. No real service activation; no customer data or credentials.
