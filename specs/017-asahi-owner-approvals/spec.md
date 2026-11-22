# Spec 017 — Owner-only tenant alert approval

## Goal
Enable an active tenant **owner** to approve or revoke opaque alert delivery references using an existing verified, active, server-side session. No raw destination access and no outbound network are enabled.

## Acceptance
- [x] Application role may call narrow SECURITY DEFINER approve/revoke routines but cannot read or modify policy tables directly.
- [x] Session digest must resolve through existing `sme.resolve_session`, including expiry, revocation and active tenant membership.
- [x] Caller must have active tenant-scoped `owner` role assignment for exactly the requested tenant; admin, manager, operator, viewer and cross-tenant identities have no approval power.
- [x] Invalid channel or unsafe references fail closed without writing.
- [x] Approval and revocation keep durable audit records; reapproval after revocation remains explicit.
- [x] PostgreSQL integration regression tests exercise authorization, non-owner, suspension, revocation, reference safety and audit.
- [ ] GitHub CI green before merge.
- [ ] Approved UI/BFF route with HTTPS, CSRF, same-origin guard and an explicit fresh MFA/step-up signal verified from trusted IdP.
- [ ] Validate secure secret-provider bindings before activating live alert delivery.
- [ ] Production security audit and real customer approval.

## Architecture
L1 future owner settings UI -> L2 authenticated server-side session digest, tenant-scoped approval -> L3 restricted PostgreSQL procedures, audit and existing lease-bound dispatch resolver.

## Threats and limits
The active session and owner role are verified in DB; **no fresh MFA/step-up is proven**. Therefore this database primitive is not authorized for unrestricted production exposure. Do not expose a browser API until the MFA trust contract is independently implemented and tested. The currently installed DB migration owner can still modify or forge audit data: immutable external evidence is not yet available. No customer credentials or delivery endpoints are stored; references remain opaque. 
