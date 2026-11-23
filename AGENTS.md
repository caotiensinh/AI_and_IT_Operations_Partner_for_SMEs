# Mandatory instructions for ALL coding agents and human contributors

This repository uses **Definition of Done v1.0** as a binding *project policy*:
[`docs/governance/definition-of-done.md`](docs/governance/definition-of-done.md).
Read this file and `.specify/memory/constitution.md` **before editing**. These instructions apply to Codex, Copilot, Claude, Cursor, other automation and humans. Tool-specific prompts may add protections but cannot weaken this policy.

## Required workflow
1. Fetch live `main`; inspect existing work and PRs. Do not overwrite concurrent edits, rebase other's branches, force push or disable a check.
2. For a feature or significant change, use existing `.specify/` and create/update versioned specs, dependencies, and **Given/When/Then** acceptance criteria **before coding**. Small fixes still require an identified regression and acceptance criteria.
3. Keep each change scoped and reversible. Create `acceptance/records/<ID>.json` using the existing ledger contract, with truthful `NOT_STARTED`/`IN_PROGRESS`/`BLOCKED` state; never fabricate `verified`, evidence, reviewers or SHA. Code without independently verified user workflow is **not** `ACCEPTED`.
4. Commit code, tests, documentation and acceptance updates to a feature branch. Run positive, negative, boundary, failure and regression tests as applicable. Include actual source SHA, exact commands, CI links, real service and browser observations; clearly label synthetic data and mocks.
5. Open a PR using `.github/pull_request_template.md` and add machine-readable `Acceptance-IDs:` / `Change-Type:` lines. Green CI is **L2 at most** unless independent integration and user acceptance exist. For PR merge, require branch ruleset approval and all required checks; do not self-approve.
6. Never merge Draft or failed/pending/stale CI PRs, or work explicitly labeled DO NOT MERGE. Never merge all branches blindly: classify ancestry, dependency, conflicts, secrets, migrations, evidence and reversible rollback; preserve original refs.
7. Do not deploy to production, claim L5, expose secrets or use live customer data without explicit owner/operator approval and the production release manifest gates.
8. Report `HOÀN THÀNH` = independently `ACCEPTED` items only, `CÒN LẠI` = all non-accepted items, `TIẾN ĐỘ CẢI THIỆN` = newly accepted items with proof. Engineering artifacts whose CI passes can be reported separately as verified components, not accepted features.

## Enforcement boundary
`pr-governance.yml` checks PR metadata and record contract on every PR. **Only GitHub repository rulesets/branch protection can make it non-bypassable**, including blocking direct pushes/admin bypass, requiring independent review and selecting required status checks. Repository owner must configure and test these server-side settings. This text alone is not an access control. If the ruleset is absent, report enforcement `BLOCKED`, not `PASS`.

For conflicts between speed and auditability, prefer fail-closed and request an authorized reviewer. See `CONTRIBUTING.md`.
