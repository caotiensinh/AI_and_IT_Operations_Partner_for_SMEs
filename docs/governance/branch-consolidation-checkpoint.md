# Consolidation checkpoint — pinned 2026-11-23 inventory

This is an observed, **read-only** inventory; it has not merged any code.

## Reproducible evidence

- Source repository: `caotiensinh/AI_and_IT_Operations_Partner_for_SMEs`
- Pinned main: `1a436502f4fff1ebc512d9eed29508888fa4d83d`
- GitHub Actions: https://github.com/caotiensinh/AI_and_IT_Operations_Partner_for_SMEs/actions/runs/45172489715
- Total branch refs: **79**, including `main`.
- Of 78 non-main refs: **38 ALREADY_INCLUDED**, **39 DIVERGED_REVIEW**, **1 UNMERGED_LINEAR_REVIEW**, **0 UNKNOWN_BLOCKED**.
- These are *git ancestry counts*, not counts of independent features or proof that any branch is safe to merge.

## Consolidation lanes and blockers

| Lane | Refs/PRs | Action needed | Merge status |
|---|---|---|---|
| Existing main ancestry | 38 refs, no unmerged commits | No code transplant needed; preserve refs until explicit cleanup | Already in main ancestry |
| Agent/human governance | `feat/mandatory-agent-human-acceptance`, PR #79 | Exact-SHA CI + independent review + owner enables server-side main ruleset | NOT MERGED |
| Discovery/OIDC stack | `integration/discovery-staging-20261122` PR #67 plus stacked PRs #19–#61 | Reconcile migrations, auth, CI workflows against latest main; full E2E and security review. PR explicitly DO NOT MERGE | BLOCKED |
| Production readiness | `feat/spec024-release-readiness-gate` PR #69 | Review 8 explicit readiness blockers; merge policy contract separately from deployment authorization only after signoff | BLOCKED |
| Browser evidence storage | `fix/acceptance-artifact-fail-closed` PR #75 | Resolve GitHub Actions artifact quota or validate durable self-hosted storage; do not hide upload failure | BLOCKED |
| Asahi security/approval and older feature branches | Other diverged refs including MFA/role/step-up and audit | Determine unique patch sets, overlapping ancestry, security impacts and exact SHA CI. Avoid duplicate replays | REVIEW REQUIRED |

## Non-negotiable integration policy

1. Always fetch current `main` before any mutation; a stale checklist does not permit merge.
2. Do not use `git merge -s ours`, overwrite whole trees, force-push `main`, delete branch refs, or falsely label code merged.
3. Build an isolated integration branch; preserve all unrelated main changes, including newer Spec 027–029 checks.
4. Inspect changes to authentication, tenant RLS, migration history, GitHub workflows and API behavior before each merge; test both normal and denial scenarios.
5. Merge into `main` only through the ruleset-protected PR path with required checks and independent reviewer approval.
6. Do not transform PR #67 (explicit DO NOT MERGE) or a production release contract into a customer deployment.

## What counts as success

The consolidation goal completes only when every original non-main ref is classified and its **unique, accepted** changes are included by traceable commits in current main, or the owner records an explicit evidence-backed decision to exclude obsolete/unsafe changes. Historical branch refs remain intact until separately authorized cleanup.

Current consolidation acceptance: **IN_PROGRESS / L0**. The verified classification is a discovery milestone, not a merged feature.
