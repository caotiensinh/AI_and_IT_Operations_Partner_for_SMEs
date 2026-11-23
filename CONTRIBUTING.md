# Contributor and Agent Operating Contract

The mandatory specification is [Definition of Done v1.0](docs/governance/definition-of-done.md). Applies equally to humans, AI coding agents and automated CI.

## Before work
- Read `AGENTS.md`, `.specify/memory/constitution.md`, existing related specs and acceptance ledger.
- Find existing modules and source branches; build from current `main`, inspect concurrent changes, select a single scoped change.
- Define explicit Given/When/Then, negative/failure paths and exclusions before implementing. Use Spec Kit for new features and major changes.

## Every PR
- Add `Acceptance-IDs: ID1, ID2` and `Change-Type: implementation|fix|docs|governance|integration` to the PR body.
- Include matching `acceptance/records/<ID>.json` for every ID and demonstrate correct schema. Missing evidence stays `IN_PROGRESS` or `BLOCKED`; never write false PASS.
- Include tested SHA, environment, positive/negative tests, security/isolation, deployment/recovery effects, and reproducible commands. A code review must be by someone other than the author; owners cannot self-approve.
- Do not merge Draft or work marked DO NOT MERGE, changes with pending/failing required checks, or requests lacking security/dependency review.
- Respect remote history; no force pushing, mass reset, branch deletion or unreviewed migration normalization. Production release uses separate manifest and L5.

## GitHub repository administrator — required one-time settings

Open **Settings → Rules → Rulesets** (or Branches → Branch protection) for `main`. Create an **active branch ruleset** with:
1. Restrict branch deletion, disallow force-push; require PR before merge and **block direct commits**, including for admins/automation where the UI supports it.
2. Require **at least 1 approval from someone other than the PR author**; dismiss stale approvals upon new commits; require conversation resolution and (when supported) Code Owner review.
3. Require up-to-date branch + exact-head required checks, including **`PR governance contract`**, security/public repo safety, integration, OIDC, PostgreSQL RLS, frontend build and all applicable browser/staging checks. Select exact displayed GitHub check names after confirming they exist; do not assume names.
4. Disallow bypass actors wherever possible; audit and document any unavoidable exceptions.
5. Confirm with a negative test: open an invalid PR missing Acceptance-IDs and verify merge is blocked; confirm direct push to `main` is rejected. A YAML CI check without an active ruleset **is not enforceable**.

These server-side controls must be configured through authorized GitHub administration. This repository cannot assert that the ruleset is active merely because this file exists.

## Consolidating branches
Enumerate all branch refs, compare to current `main`, classify as **ALREADY_INCLUDED**, **UNMERGED**, **DIVERGED**, **CONFLICT**, **BLOCKED_FOR_REVIEW**, or **SAFE_CANDIDATE**. Do not count stale unmerged stacked PRs as independent changes; integrate their dependency chain exactly once in a dedicated staging branch, inspect migrations/security, run full tests on exact integrated SHA, request independent review, then merge through a protected PR. Never delete branch refs to make the count look good.

## Reporting
Publish accepted IDs / remaining IDs, this-session newly accepted IDs, blockers and CI links; clearly distinguish an implemented component from an accepted product.
