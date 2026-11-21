# Spec 003 — SME Business Needs Research & Discovery (Draft)
Date: 2026-11-21 | Based on four Chubu digital-talent matching briefs | Status: proposed; extends foundation Spec 001, does not supersede security requirements.

## Goal
Turn heterogeneous SME operational pain points into an evidence-linked, permission-aware needs assessment and phased transformation recommendation. Start as a consultant-assisted workflow; avoid a monolithic ERP or premature industry product commitments.

## Personas
SME decision maker, department manager, operator/interviewee, scoped external DX advisor, tenant auditor. Global support remains metadata-only absent approved time-limited access per Spec 001.

## User journeys
1. Advisor creates a tenant-scoped research case, registers company sector, business process, problem statements and source documents with evidence level E/I/V.
2. Operator validates As-Is steps, handoffs, systems, manual effort, known errors, and confidentiality constraints.
3. Advisor records root causes and alternatives (keep, integrate, buy, build, replace, defer), expected benefits, effort, risks and migration consequences.
4. Manager approves a To-Be/PoC scope with a baseline KPI, test plan and budget ceiling; rejected options and rationale stay auditable.
5. Team records pilot outcomes, owner acceptance and handoff; proposals are never auto-activated into customer production.

## Functional requirements
BR-FR-001: A research case MUST have tenant, scope, owner, source provenance, evidence classification and explicit confirmation status.
BR-FR-002: Every requirement has unique ID, original statement/translation, company/source page, classification (explicit/inferred/unverified), priority and approval state; inferred items cannot silently become customer commitments.
BR-FR-003: Capture As-Is process map, task actors, manual work, duplicate entry, data sources and measurable baseline; missing information MUST be displayed, not fabricated.
BR-FR-004: Produce alternatives: keep/integrate/buy/build/replace/defer; compare cost, implementation risk, staff impact, vendor lock-in, data handling and reversibility.
BR-FR-005: The tool MUST support clear negative scope rules (e.g., Ryoki production/accounting/HR systems not replaced; Beight no assumed rewrite; JTEKT no up-front tool selection).
BR-FR-006: Track To-Be proposal, testable acceptance criteria, approval identity, change history and phased PoC with abort/rollback strategy.
BR-FR-007: Each KPI defines calculation, baseline time window, target, data origin, owner and validation status. Missing numbers remain unknown.
BR-FR-008: Reuse platform auth/RBAC, tenant RLS, audit, storage and permitted AI providers. No raw customer document leaves approved boundary without explicit authorization.
BR-FR-009: Industry-specific capability packs are optional plug-ins, independently enabled and never prerequisites for core discovery.
BR-FR-010: Export a sanitized decision pack: source-linked risk/requirements matrix, As-Is/To-Be, scored options, PoC plan, ownership and unverified assumptions.

## Non-functional and security
- No production connector writes at discovery stage; default-deny and customer-approved service accounts.
- No use of the original confidential files as public test fixtures. Synthetic records for automated tests.
- Japanese initial UI, Vietnamese/English localization per foundation; low-click, accessible input on desktop/tablet/mobile.
- Do not claim business ROI until real before/after measurements are reviewed.
- Preserve existing platform architecture nomenclature: L1 Business & Experience, L2 Domain & Application Services, L3 Platform & Infrastructure.

## Non-goals
Full salon POS/CRM, BPR enterprise suite, manufacturing ERP, Microsoft 365 replacement, autonomous production changes or customer data access without authorization.

## Acceptance criteria (proposed, NOT currently met)
AC-01: Sample B/J/L/R research cases import with distinct industry boundaries and original source labels.
AC-02: Every inferred requirement is visibly marked unconfirmed in UI, exports and API.
AC-03: JTEKT journey builds an As-Is/To-Be pilot without compulsory technology choice or exhaustive inventory.
AC-04: Ryoki case rejects proposal to replace manufacturing, accounting or HR; Beight rewrite requires owner approval.
AC-05: Cross-tenant and role misuse cannot access case data, attachments, exports, search results or AI prompts.
AC-06: Cost/KPI reporting refuses to label missing measurements as verified savings.
AC-07: Pilot closeout requires evidence, decision maker acknowledgment and knowledge transfer record.

## Research source
See `docs/research/2026-11-chubu-sme-four-case-study.md`, `docs/research/requirements-traceability-matrix.md`. Original four PDFs were provided by the user privately; they are not stored here. Obtain explicit permission and assess confidentiality before publishing further excerpts.
