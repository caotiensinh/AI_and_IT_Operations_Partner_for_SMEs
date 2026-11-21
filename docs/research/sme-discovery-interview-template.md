# SME Digital Transformation — discovery interview template (BN-002)
Version 1.0 | Status: reusable consultant worksheet, NOT answers from any of the four companies.

## 0. Engagement consent and boundaries
- Interview date, stakeholder role, company/site (avoid unnecessary personal identifiers)
- Purpose and usage permission; recording and data retention permission; NDA and approved storage
- Systems/data that cannot be accessed, copied, replaced, or shared with external AI
- Project owner, decision maker, procurement contact (store in private tenant workspace only)
- Explicitly distinguish interviewee statement, supporting evidence and consultant hypothesis

## 1. Business outcome (ask decision maker)
1. What outcome must improve in the next 3/6/12 months? Why now?
2. Which three workflows cause the most friction? What happens when unchanged?
3. What evidence currently proves the problem? Can we measure baseline without copying sensitive content?
4. What does a failed project look like? List non-goals and protected systems.
5. Who can approve an experiment, a production change, a recurring charge or a new data processor?

## 2. As-Is workflow (ask frontline operator)
1. What event starts the work and what counts as completion?
2. Walk through steps, roles, handoffs, approvals, exception paths and rework.
3. Which fields are entered more than once? In what software, sheet or paper form?
4. Volume/week, minutes/item, error/rework rate, backlog, staffing, peak periods (mark UNKNOWN if not measured).
5. Where are authoritative records? Who can view/change/export them? Is there a recovery procedure?
6. What is hardest for a new staff member to learn? Which knowledge lives only in one person's memory?

## 3. IT and data discovery (ask system owner)
1. List existing software, OS/platforms, devices, licenses, data owners and API/export capability.
2. Identify systems that must stay, integrations that are permitted, and vendor-imposed limits.
3. Classify data (personal, financial, HR/payroll, engineering IP, trade secret, public) and retention.
4. Identity, MFA, departmental roles, external sharing, audit, backup, restore evidence and recovery targets.
5. Cloud/on-prem/hybrid, network outage tolerance, mobile/field constraints, accessibility/language.

## 4. Solution choice and measured value
1. Evaluate KEEP / INTEGRATE / BUY / BUILD / REPLACE / DEFER, including migration risks.
2. Capture cost assumptions: staff hours, subscription, integration, training, ongoing support, downtime.
3. Define baseline, formula, sampling period, target and person validating each KPI.
4. Agree one reversible low-risk PoC: scope, synthetic/sanitized data, stop condition, fallback.
5. Name approver for changes; record review date and sign-off. Do NOT fill missing answers from AI guesses.

## 5. Industry-specific supplements
**Beight / salon:** customer journey, reservations, photo/consultation consent, source of truth for LINE/POS, staff handoffs, repeat rate definition; no automatic SIEVE OS rewrite.

**JTEKT / SSC-BPR:** one process As-Is -> causes -> To-Be; client pain, service hypothesis, cost/profitability and reusable OJT; do not begin with tool selection.

**Liveall / small manufacturing:** actual Access schema & backups, production daily-report fields, planning constraints, Excel/paper duplication, shop floor input devices and build-vs-buy.

**Ryoki / industrial M365:** document classes, SharePoint/OneDrive permissions, Copilot oversharing, groupware migration downside, bookings/approval routes; production, accounting and HR remain in place.

## 6. Evidence packet for each problem
`Requirement ID | owner | original statement | exact source/page or interview session | evidence class (explicit/inferred/unverified) | baseline | requested change | constraints | priority | decision | acceptance test | status`.

**STOP:** An unverified assumption is never a committed requirement, and an unsigned proposal is never deployment authorization.
