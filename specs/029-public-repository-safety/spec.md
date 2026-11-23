# Spec 029 — Public repository safety gate

## Context
On 2026-11-22 GitHub API returned `private=false`, `visibility=public`. Repository exposure increases the consequence of a tracked secret or private key. Existing `.gitignore` excludes local dotenv files but does not prevent force-added or previously committed secrets. Five product acceptance records remain 0/5.

## L1 / L2 / L3 acceptance criteria (Given/When/Then)
- **AC01 (positive):** Given normal tracked source and placeholder-only `.env.staging.example`, when CI scans `git ls-files`, then the command returns zero, reports files inspected, and does not declare historical/production security.
- **AC02 (negative):** Given a tracked private-key block, known credential token, non-placeholder staging-example secret, `.env`, key store or credentials file, when scanner runs, then CI fails without printing the credential.
- **AC03 (boundary):** Given symlinks, missing files, oversized files or path traversal in tracked inventory, scanner fails closed and refuses to certify unreadable content.
- **AC04 (regression):** Given an actual disposable Git repo, a safe tracked file yields zero and adding a restricted `.env` yields nonzero; negative unit tests run before scan.
- **AC05 (reporting):** Given all CI jobs PASS, report *tracked checkout guard verified (L2)*, not historical Git secret cleanliness or public security acceptance.
- **AC06 (independent backlog):** Independent human/security owner must inspect all refs/history, forks, public Actions artifacts, logs, GitHub security settings and rotate any discovered exposed credentials before signing broader security readiness.

## Implementation
- `scripts/check_public_repo_safety.py`: no dependencies; scans only tracked working-tree files and prints findings without secret values.
- `tests/test_public_repo_safety.py`: positive, negative, boundary and genuine Git index tests.
- `.github/workflows/public-repo-safety.yml`: triggers for every push and pull request with read-only token, avoids persisting checkout credentials.
- `SECURITY.md`: private vulnerability disclosure guidance and explicit scope limits.

## Exclusions and immutable evidence
No production changes, credential rotations, artifact deletions, Git history rewrite or branch protection mutation. Never alter existing evidence records to ACCEPTED from a clean filename scanner. Public visibility does not resolve existing GitHub Actions artifact quota.

## Verification checklist
- [x] Baseline and concrete criteria defined
- [x] Source and tests committed to isolated branch
- [ ] PR exact-head automated tests PASS
- [ ] Current main SHA checked before safe merge
- [ ] Historic secret exposure and public artifact review independently completed (outside this spec's implementation gate)
