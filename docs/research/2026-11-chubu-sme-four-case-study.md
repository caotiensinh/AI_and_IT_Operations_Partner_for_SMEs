# Four Japanese SME DX project sheets — evidence-based business needs study
Date: 2026-11-21 | Language: Vietnamese | Status: secondary analysis, **not customer validation or purchase commitment**

## Provenance and guardrails
Four user-supplied, one-page project sheets from 中部経済産業局 デジタル人材マッチングイベント: `pj_Beight.pdf`, `pj_jtekt.pdf`, `pj_liveall.pdf`, `pj_ryoki.pdf`. Each is a company-authored recruitment/project brief. Conclusions are limited to those sheets; no interviews, system access, procurement approval, contract, or pilot has occurred. The PDFs were supplied privately; **do not redistribute source documents, employee/customer data or internal contact details**. Statements below marked **[E]** are explicitly supported by the source sheet, **[I]** are product/engineering inferences, **[V]** require validation. A need for external help is not proof of demand for our SaaS. Fee ranges are advisory contractor compensation, not product budgets.

## Case B — 株式会社Beight / SIEVE HAIR (Ichinomiya; salon)
**Problem [E]:** Reservation, customer, counselling, service history and LINE information are fragmented; handovers/customer care rely on staff memory. AI-assisted SIEVE OS remains a prototype. Needs production database/integration/security, code/test review, incident readiness and specialist technical leadership.
**Target outcomes [E]:** Per-customer reservation, treatments, counselling/photos and post-visit follow-up; shared priorities/task completion; revisit frequency, repeat rate and LTV analysis; test at own salon before considering other salons.
**Requested engagement [E]:** Diagnose existing JavaScript web app, API/DB and risks; evaluate PC/mobile data sharing, backup, external integrations, secure development and QA; prioritized, cost/risk-aware production roadmap. Preserve confirmed specifications and existing assets; changes require owner approval. Deliver technical assessment, risk register, priorities and roadmap (NOT immediate rebuild).
**Candidate capabilities [I]:** read-only architecture/code audit, consent/privacy inventory, tenant-aware data mapping, backup restore verification, deployment rollback, LINE/POS adapters after contractual/API checks.
**Validation [V]:** actual source architecture, data classes, integrations, salon workflow, contractual permission, retention, budget and KPIs.

## Case J — ジェイテクトサービス株式会社 / JTEKT Service (shared-services)
**Problem [E]:** Payroll/HR, general affairs, facilities, security, grounds services retain manual/individual methods; limited cross-workflow analytics and reusable BPR method; service expansion should not simply add headcount.
**Target outcomes [E]:** Standardize and redesign existing business, identify group customer unmet needs, improve profitability, and transfer methods so staff can run subsequent projects.
**Requested engagement [E]:** Start with one priority process, simplified As-Is -> causes -> options -> To-Be; examine one service hypothesis; estimate benefits, person-hours, business case, risks and small PoC. Do not start with exhaustive process mapping or technology selection. Produce decision material and reusable templates/OJT. Initial target 3–6 months, approximately one case; planned from Apr 2027 subject to budget and internal approval.
**Candidate capabilities [I]:** process discovery templates, evidence-linked BPR workspace, ROI scenario calculator, reusable playbooks, approval-aware AI assistance.
**Validation [V]:** approved sample business process, baseline effort/quality, data-use approval, decision makers and success threshold.

## Case L — 株式会社ライブオール / Liveall (Kasugai; ~40 employees; food-packaging film)
**Problem [E]:** Legacy Microsoft Access core plus Excel and paper reports; duplicate entry/handwriting; no dedicated digital professional, and hiring full-time is impractical.
**Target outcomes [E]:** Digitize (1) production work diaries, (2) production planning, (3) accounting office work, (4) other back office; reduce work time and paper. May build in-house OR select existing services.
**Requested engagement [E]:** Generalist recommending practical build-vs-buy options with the project contact. Indicative consultant fee ~JPY 50k/month, initial ~6 months; **not software budget**.
**Candidate capabilities [I]:** process and data-entry maps; Access/Excel import/export; minimal production reporting forms; safe read-only legacy connector first; on-prem/offline option if required.
**Validation [V]:** Access schema/version and write path, report templates, production constraints, regulatory accounting dependencies, offline requirements, licensing, baseline time saved and investment ceiling.

## Case R — 菱輝グローバルツーリング株式会社 / Ryoki Global Tooling (aerospace CFRP tooling)
**Problem [E]:** Independent systems for production, information sharing, documents, groupware, accounting and HR; new production site motivates consolidation. Most PCs can use Copilot; Microsoft 365 (OneDrive, SharePoint, Forms) is preferred for replaceable document/groupware functions.
**Target outcomes [E]:** Find specifications, procedures and rules without tribal knowledge; route approvals, proposals and defect reports; resource bookings (rooms, company cars, transport); notices and groupware migration. **Production management, accounting and HR are explicitly not slated for replacement.**
**Requested engagement [E]:** Hands-on evaluation of migration feasibility AND disadvantages, build/configure agreed target and support adoption. Sensitive technical information requires careful leakage prevention and confidentiality agreement. Indicative consulting fee JPY 100k–150k/month, initial ~6 months; **not software budget**.
**Candidate capabilities [I]:** M365 governance/migration assessment, least-privilege SharePoint/Entra controls, approved workflows, document permission inventory, Copilot oversharing review.
**Validation [V]:** actual tenant licensing, data classification/export restrictions, migration corpus, security policy and compliance requirements, adoption baseline.

## Cross-case synthesis
| Need | Beight | JTEKT | Liveall | Ryoki | Interpretation |
|---|---|---|---|---|---|
| Expert-led discovery and phased decisions | E | E | E | E | Common service delivery capability |
| Preserve/reuse existing systems | E | E | E | E | Integration-first / build-vs-buy |
| Reduce manual work/knowledge silos | E | E | E | E | Different domain workflows |
| Data connection/visibility | E | E | E | E | Heterogeneous boundaries |
| Security/information governance | E | E | I | E | Depth and obligations vary |
| Measurable business impact | E | E | E | E | Must capture baseline and evidence |
| AI adoption | E | I | I | E | **Not universal AI requirement** |
| One replacement ERP | No | No | No | Explicitly no for three systems | Do not make ERP replacement a default |

Here E = explicitly described or directly entailed, I = analyst hypothesis, No = not a requested scope. Table summaries are qualitative, not market statistics.

## Product implications (hypotheses, not customer requests)
1. **Assessment + improvement workflow first:** intake -> baseline -> evidence -> risk/prioritization -> proposal -> scoped PoC -> ROI -> adoption/operations.
2. **Reusable platform services:** org and role scope, source/permission registry, workflow/task/approval, connector SDK, document index/knowledge, evidence and outcomes, security/audit/backup.
3. **Distinct industry packs:** salon CRM + LTV (B), BPR/service hypothesis (J), work diary/production planning (L), M365 governance/migration/bookings (R). Domain-specific schemas/workflows remain separate.
4. **Non-disruptive interoperability:** read-only before write, customer approval for source changes, reversible mappings, no replacing systems with explicit retention decisions.
5. **AI as assistive layer:** explain and cite evidence, human approval before production mutation; strict customer-data and provider policy. Never upload confidential materials to unapproved models.

## Commercial interpretation and research risks
These are recruitment opportunities for consultants and do **not** establish willingness to buy a standardized tool. Test assessment-service demand, delivery cost and measurable ROI before expanding SaaS scope. Avoid inferring number of seats, ARR, budget, deployment preference, or compliance certifications from the forms.

## Next research
Interview at least one decision maker and one operator per eligible pilot, with permission. Capture task frequency/time, duplicate input rate, error costs, current tech and constraints, data classifications, procurement process, and quantified definition of success. Keep source traceability and distinguish interviews from proposal assumptions.
