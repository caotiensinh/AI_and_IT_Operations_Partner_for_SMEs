# Spec 019 — Single-use Asahi owner-approval step-up proof

## Mission
Close the remaining *database bypass* in Spec 018: ownership and an ordinary valid session alone must no longer be enough to approve or revoke alert routing. Require a narrowly issued, **one-use, short-lived, tenant-, session-, action-, and payload-bound** server-side proof.

## L1–L3 architecture
- **L1 UI:** Not connected. No customer-facing approval API is deployed by this change.
- **L2 trusted IdP/MFA verifier:** NOT IMPLEMENTED; a future separate service must verify *fresh* MFA with the configured identity provider and bind the actual authenticated session, tenant and precise action. The DB issuer is not a substitute for IdP MFA.
- **L3 PostgreSQL:** `sme_stepup` NOLOGIN issuer role and `sme_approval` NOLOGIN action role; only an approved separately credentialed service may be granted access after IdP verification. The policy database owns atomic single-use state and persists audits from Spec 016/017. Legacy owner functions are revoked from all application and approval runtime roles.

## Scope implemented
- One-use UUID proof records with immutable binding fields (including opaque destination and secret references), issued only for active session + tenant-scoped owner.
- TTL between 15 and 120 seconds, checked at consumption time; consumed under one atomic `UPDATE ... WHERE consumed_at IS NULL ... RETURNING`.
- Separate action-bound approve and revoke procedures. On consume they *re-check current session and owner role* via existing trusted procedures; revoked session or ownership denies.
- No runtime grants on proof table. Issuer and approver separated: `sme_stepup` cannot approve and `sme_approval` cannot issue.
- Integration regression for replay, action mix-up, destination changes, tenant/session mismatch, expiry, invalid refs, revoked sessions, non-owners, and legacy bypass.

## Acceptance
- [x] SQL migration + tests committed to a dedicated branch and PR.
- [ ] CI tests GREEN on exact head SHA; only then merge.
- [ ] Independent, provider-verified fresh MFA/step-up, proof authenticity, binding to an unforgeable browser session and redirect/callback.
- [ ] Production least-privilege service credentials, configured from secret manager and reviewed provisioning.
- [ ] HTTPS BFF, Origin/CSRF/SameSite checks, rate limits, replay and concurrent action browser tests.
- [ ] Real enterprise IdP test, external audit export, and production operator rollout.

## Operational safety
No approval service role is usable by normal applications by default because both roles are `NOLOGIN`. This migration **does not claim MFA has occurred**. CI uses a privileged disposable PostgreSQL migration/test connection to simulate the trusted issuer: this is a test only, never a production credential path. Migration owner can still change proof or audit rows. Opaque reference values are not live network URLs or secrets. No outbound alerts.
