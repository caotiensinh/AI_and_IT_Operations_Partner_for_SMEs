# Main branch ruleset — owner activation and verification

**Status as of 2026-11-23:** `GET /repos/caotiensinh/AI_and_IT_Operations_Partner_for_SMEs/rulesets` returned `[]`. The repository connector does **not** offer ruleset administration write access. The audit workflow intentionally fails closed; no ruleset has been activated by this PR.

GitHub's official ruleset REST endpoint requires repository **Administration: write** permission: https://docs.github.com/en/rest/repos/rules#create-a-repository-ruleset .

## Owner-only, reversible rollout

1. Review [AGENTS.md](../../AGENTS.md), the Definition of Done, and the required check names already produced by actual GitHub Actions runs. Do not mark path-filtered workflow checks mandatory for every PR because they may never run on docs-only PRs.
2. With an authorized, scoped admin credential on the operator machine (never commit a token), read live main:
   ```sh
   gh auth status
   gh api repos/caotiensinh/AI_and_IT_Operations_Partner_for_SMEs/branches/main --jq .commit.sha
   gh api repos/caotiensinh/AI_and_IT_Operations_Partner_for_SMEs/rulesets
   ```
3. Supply the retrieved SHA and execute **dry-run** first:
   ```sh
   export GITHUB_TOKEN="$(gh auth token)"
   python scripts/install_main_ruleset.py --expected-main-sha <LIVE_FULL_MAIN_SHA>
   ```
4. Only after reviewing the proposed **active** rule and confirming an independent reviewer is available:
   ```sh
   python scripts/install_main_ruleset.py --expected-main-sha <LIVE_FULL_MAIN_SHA> --apply --confirm-repository caotiensinh/AI_and_IT_Operations_Partner_for_SMEs
   unset GITHUB_TOKEN
   ```
   The script rejects a changed main SHA or pre-existing active branch rules. Ambiguous POST timeout means **UNKNOWN**: inspect GitHub rulesets before trying again. Never blindly retry.
5. Verify **actual server-side enforcement**, not just an API response. Re-run `python scripts/audit_main_ruleset.py` with an authorized read token; ensure its output is PASS. Then open a disposable invalid PR missing Acceptance-IDs and verify the merge UI blocks it. Attempt a harmless direct main push from an authorized maintenance environment and confirm GitHub refuses; do not use force push or bypass to test. Inspect audit trail. If tests fail, treat `GOV-ENFORCEMENT` as BLOCKED, investigate before any merge.
6. If the owner needs rollback after accidental lockout: use Settings → Rules → Rulesets, inspect the exact named rule, temporarily **disable** it using admin access and document the reason. Do not remove branch history or delete workflows.

## Required rules
- Target only `refs/heads/main`.
- No bypass actors.
- Pull request, at least one independent approving review, stale review dismissal, last-pusher approval requirement and discussion resolution.
- Require the checks **PR governance contract** and **Public repository tracked-file safety**, with latest-main sync.
- Block deletion and non-fast-forward (force pushes).
- Other E2E/DB/production checks should be required using an always-running aggregate workflow or additional scoped rules; the current path-filtered workflows cannot be indiscriminately required in every PR.

## Boundaries
CI success does not equal user acceptance or authorization to deploy. The installer is an **operator tool**; it intentionally does not run automatically on PRs. No ruleset exists until a GitHub administrator has executed and verified installation. Independent review of exact HEAD and acceptance-record evidence remain mandatory.
