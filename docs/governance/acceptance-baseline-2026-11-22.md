# Acceptance baseline — 2026-11-22 (no retroactive completion)

**Policy:** [Definition of Done](definition-of-done.md). This is an inventory of evidence, **not** independent user acceptance. `python scripts/check_acceptance.py` validates structure, not truthfulness of URLs or operator sign-off. The CI result must be inspected, and every claim must reference the same scope and code revision.

## Measured status vs target

| ID | Scope | Current | Acceptance target | Evidence / missing |
|---|---|---|---|---|
| UI-OVERVIEW | Authenticated overview | L1 / IN_PROGRESS | L4 / ACCEPTED | UI test on synthetic data exists, but no independent authenticated staging screenshots/review, restart validation or operator sign-off |
| UI-ASSETS | Tenant-scoped assets | L1 / IN_PROGRESS | L4 / ACCEPTED | No signed independent UI acceptance |
| UI-MONITORING | Latest tenant telemetry | L1 / IN_PROGRESS | L4 / ACCEPTED | No approved operational staging evidence |
| SEC-ASAHI-STEPUP-E2E | Owner MFA approve/revoke/audit | L2 / IN_PROGRESS | L4 / ACCEPTED | [PR #73](https://github.com/caotiensinh/AI_and_IT_Operations_Partner_for_SMEs/pull/73) passed synthetic signed MFA + real PostgreSQL logins; real IdP/HTTPS UI absent |
| SEC-ASAHI-READINESS | Step-up security and role preflight | L2 / IN_PROGRESS | L5 / ACCEPTED | [PR #70](https://github.com/caotiensinh/AI_and_IT_Operations_Partner_for_SMEs/pull/70) and [PR #71](https://github.com/caotiensinh/AI_and_IT_Operations_Partner_for_SMEs/pull/71) show component/staging-role gates only; live production controls absent |

**Denominator:** exactly 5 enumerated acceptance IDs. **Accepted: 0/5. Remaining: 5/5.** New records are backward-looking evidence baselines, not feature approvals.

## Required evidence before comparing “expected vs actual”
For each `AC-xx`, record:
1. **Given/when/then** and objective expected value, negative behavior, boundary and failure/recovery conditions.
2. Exact **commit SHA** checked, environment type (mock/synthetic CI/deployed staging/production), input fixture, command, test result and CI run.
3. Actual observed persisted state and audit, rejection logs without secrets; a screenshot is not evidence of database state.
4. For UI, real Chromium captures at 1440×900, 820×1180, 390×844 and 320×640, with exact SHA, authenticated workflow, tenant A/B isolation and denied-session state.
5. Deployment restart, backup restore and rollback drill when applicable.
6. Independent named human approval on exact SHA/environment; for production also the owner and operational release gates.

## Known evidence storage blocker
The browser job on acceptance-governance PR #72 initially produced **13 real Chromium screenshots plus manifest** but the upload failed because **GitHub Actions artifact storage quota was reached**. The workflow now distinguishes a passing browser assertion from a failed artifact archive, with explicit `EVIDENCE_ARCHIVE=FAILED` warning. Do not elevate UI levels without retrieving and reviewing the actual captured files from a successful run and saving the approved long-lived evidence.

## Reporting standard
- **HOÀN THÀNH:** only ACCEPTED IDs, not merged PRs.
- **CÒN LẠI:** every non-ACCEPTED ID and its specific unmet gates.
- **TIẾN ĐỘ CẢI THIỆN PHIÊN VỪA RỒI:** count of newly accepted IDs verified at identical denominator. Development changes may be separately noted as merged/CI PASS; never conflate.
- **BLOCKED:** external prerequisites only, with explicit steps to unblock and independent work remaining possible.

## Next acceptance task
Run the real SME workspace over a deployed HTTPS staging ingress with registered test IdP and documented service users, retain durable UI evidence, and have an independent operator compare real API/database state to UI and sign off. Until this exists, L4 and L5 cannot be claimed.
