# Requirements traceability — four SME business cases
Status: research baseline; none accepted by a customer. Source IDs refer to the four privately supplied one-page project sheets: B=Beight, J=JTEKT Service, L=Liveall, R=Ryoki. E=explicit statement, I=inference, V=requires validation.

| ID | Company | Stated need / outcome (E) | Candidate platform/domain response (I) | Required validation | Acceptance artifact / test proposal |
|---|---|---|---|---|---|
| B-01 | Beight | Customer-centric reservation/treatment/counselling/follow-up | Salon connector and Customer 360 domain | Data ownership, consent, identifiers, API access | Test isolated customer journey on sanitized records, signed off by salon |
| B-02 | Beight | Productionize current SIEVE OS without rebuild | Read-only code/DB/security/QA assessment | Existing code/tests and approved architecture | Risk register with code/evidence links, priority and owner |
| B-03 | Beight | Safe PC/mobile data, backups and integrations | API contract and recovery assessment | Recovery objectives, synchronization source of truth | Restore drill and cross-device consistency evidence |
| B-04 | Beight | Staff priorities and repeat rate/frequency/LTV | Task/analytics domain, not generic monitoring | KPI definitions and available input | Reproducible KPI calculations and acceptance |
| J-01 | JTEKT | One focus process As-Is/causes/To-Be | BPR workspace + reusable templates | Approved process and stakeholder roles | Signed-off baseline, root causes, future-state draft |
| J-02 | JTEKT | Compare options by effort, outcome and risks | Scenario/benefit decision record | Time-cost baselines and assumption owners | Alternative comparison with assumptions and sensitivity |
| J-03 | JTEKT | Internal self-sufficiency/OJT | Template/playbook repository and reviews | Staff skill and operating cadence | Staff complete next sample without outside authorship |
| J-04 | JTEKT | One service hypothesis and small PoC plan | Opportunity hypothesis tracker | Customer data-use authorization | Assumptions, costs, PoC stop/go and decision memo |
| L-01 | Liveall | Digitize factory work diary | Lightweight manufacturing work diary adapter | Source forms, shop-floor usage and devices | End-to-end diary without duplicate entry in pilot |
| L-02 | Liveall | Digitize production planning | Planning workflow and import/export | Scheduling constraints/Access records | Reproduce accepted planning sample on anonymized data |
| L-03 | Liveall | Digitize accounting/back-office | Build-vs-buy process recommendation | Compliance, accounting vendor and audit | Approved option assessment; no premature replacement |
| L-04 | Liveall | Replace repeat entry/paper gradually | Read-only Access/Excel profiling then staged mapping | Database backup/schema/access authorizations | Zero unintended writes, reconciliation and rollback |
| R-01 | Ryoki | Consolidate doc/groupware into M365 | M365 document governance/migration | License, security classification and migration map | Permission-preserving test migration, source/target counts |
| R-02 | Ryoki | Approvals, improvement and defect reports | M365 workflow proposal | Routing and evidence retention policy | Test each authorized approval path and refusal case |
| R-03 | Ryoki | Room/car/transport reservations and notices | M365 scheduling/intranet configuration | Concurrency, calendars and retention | Double-book prevention and mobile usability check |
| R-04 | Ryoki | Protect sensitive technical data | Confidentiality-aware least privilege | NDA, access policy and approved platform controls | Negative unauthorized sharing/search/AI-access tests |
| R-05 | Ryoki | Keep production/accounting/HR systems | Explicit no-replacement integration boundary | System list, existing contracts | Migration scope excludes all three systems |

## Shared requirements proposed for Spec 003
| Shared ID | Candidate requirement | Evidence | Acceptance gate |
|---|---|---|---|
| CR-01 | Structured discovery captures As-Is, actor, handoffs, data sources and baseline | B,J,L,R | One complete interview-derived case, missing fields visible |
| CR-02 | Decision register compares keep, integrate, buy, build, replace, or defer | B,J,L,R | Signed decision showing constraints, costs, risks and owner |
| CR-03 | Trace needs -> assumptions -> solution -> test evidence | B,J,L,R | Traceability export with no unlabeled assumptions |
| CR-04 | Tenant/role-scoped findings, documents, connectors and AI context | B,R especially; platform security baseline | Cross-tenant and unauthorized-role negative tests |
| CR-05 | Read-only connector preflight and write approval/rollback | B,L,R | Writes denied by default, contract tests and rollback evidence |
| CR-06 | KPI baseline/target/measurement and cost-benefit evaluation | B,J,L,R | Formula, sample size, time window and approver recorded |
| CR-07 | Knowledge handoff, reusable templates and adoption tracking | J,R especially | Operator acceptance and handoff exercise |
| CR-08 | Explicit domain modules with common API and no forced ERP migration | B,J,L,R | One domain can disable without affecting another |

## Evidence discipline
No acceptance check above has been executed. These are planned tests. Real customer artifacts require permission; use synthetic/sanitized examples until agreements are in place. Documents are not proof of user demand, paid acquisition, compliance approval or production readiness.
