# Spec 003 — dependency-aware research and implementation backlog

All tasks OPEN; documentation is a research baseline, not a functional MVP.

| ID | Scope | Dependencies | Verification / acceptance |
|---|---|---|---|
| BN-001 | Register source provenance and evidence E/I/V with access policy | Spec 001 tenant model | Each requirement links to source company/page, negative cases reject unsupported label |
| BN-002 | Draft reusable SME interview/discovery questionnaire | BN-001 | Covers workflows, baseline effort, systems, sensitivity, budget, approvals and non-goals |
| BN-003 | Implement scoped research-case and requirement records | M1 auth/RLS gates, BN-001 | Cross-tenant/role tests for CRUD, export, search, attachment |
| BN-004 | As-Is/To-Be and root-cause capture prototype | BN-003 | Complete one JTEKT-like synthetic process without choosing tools |
| BN-005 | Keep/integrate/buy/build/replace/defer decision model | BN-004 | Cost/risk/reversibility comparison; unsupported numeric metrics remain unknown |
| BN-006 | Constraints/explicit exclusions validation | BN-003 | Ryoki excluded systems cannot enter replacement proposal; Beight rewrite approval needed |
| BN-007 | KPI and ROI evidence schema | BN-003 | Computed metrics link to baseline/time-window/origin, no fake gains |
| BN-008 | Permissions-aware synthetic source connector registry | BN-003, secure integration kernel | Read-only default; unauthorized write denied; mutation audit |
| BN-009 | Case review, sign-off and knowledge transfer | BN-004, BN-005, BN-007 | Decision pack export and recorded acceptance |
| BN-010 | UI UX journey and accessibility test | BN-003, BN-009 | Japanese-first role flows at desktop, tablet, mobile |
| BN-011 | Four archetype fixtures and regression suite | BN-003–BN-010 | AC-01 through AC-07, positive/negative test evidence |
| BN-012 | Business validation and commercial interviews | BN-002, customer authorization | Documented interviews/consent, actual cost and ROI; no unsupported SaaS demand claim |

## Sequence
Research (BN-001/002) -> secure model (BN-003) -> parallel workflow/constraints/KPI/connectors (BN-004/006/007/008) -> decision + acceptance (BN-005/009) -> UX and regression (BN-010/011) -> authorized real-world validation (BN-012).

This is not a replacement for the existing M1 security and identity work. No production deployment before cross-tenant denial, audit, approved access and recovery proof.
