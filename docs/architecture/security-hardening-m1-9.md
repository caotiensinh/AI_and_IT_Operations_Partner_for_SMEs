# M1.9 — Membership privilege escalation regression

## Root cause
Migration 0001 granted INSERT, UPDATE and DELETE on `sme.memberships` to the ordinary application DB role. Although tenant RLS blocked cross-tenant rows, an application-role compromise or SQL injection could change membership within a selected tenant. Memberships control access and must not be modified by the read/write resource role.

## Implemented
- Correct initial migration 0001: runtime role gets SELECT on membership only.
- Add migration 0007: revoke write privileges for existing databases.
- Test runtime role cannot self-enroll, modify or delete membership; all administrative provisioning stays with separately audited privileged service.
- Existing OIDC login, protected API and audit functions remain on their assigned roles.

## Remaining
- Verify operator provisioning writes with step-up MFA, support grants and immutable audit.
- Treat server role misuse and untrusted `sme.tenant_id` as high risk: SQL RLS is a second line behind trusted API authentication, not a substitute for secure query construction and separated credentials.
- Runtime account production login credentials must be provisioned with least privilege, never a superuser.
