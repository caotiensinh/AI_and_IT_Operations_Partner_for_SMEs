# Spec 030 — Public Git history credential safety gate

## Why
The repository is now publicly accessible. The existing tracked-file guard inspects only the current checkout, which cannot detect credentials accidentally committed then deleted, or code that remains on divergent branches. An earlier tracked-file PASS must never be misrepresented as a complete public exposure audit.

## Target vs actual: testable acceptance criteria
- **AC-01 Reachable history:** GitHub Actions shall fetch all available origin heads and tags and inspect all objects reachable from all local/remote refs; a deleted .env or key file must still trigger a failure.
- **AC-02 Independent branch:** A credential-looking token reachable only on a non-main branch must be found even if it never merged into main.
- **AC-03 Sensitive bytes:** The audit must refuse dangerous tracked pathnames, private-key blocks, known credential token patterns, and oversized uninspected blobs. Logs must not print secret values or content snippets; only object IDs, filenames, reason codes and aggregate statistics.
- **AC-04 Determinism/failure handling:** Broken Git metadata or missing refs must produce a nonzero exit. Disposable fixture tests must cover clean, deleted, cross-branch and oversized cases.
- **AC-05 Regression:** The existing tracked-current-file safety job continues to run. Both jobs must pass at the exact PR head before merging; a PASS does not mean credentials never leaked.
- **AC-06 Exposure response:** On detection, revoke/rotate suspected active credentials *before* contemplating history rewrite, with a separate owner-approved plan. No force push, deletion, or history mutation is authorized by this change.

## Scope and boundaries
Read-only CI: `scripts/check_public_git_history.py`, disposable tests, and GitHub workflow. No modification of application/runtime code. Heuristic token detection cannot cover entropy-only secrets, encrypted files, GitHub PR comments, already deleted/GC objects, forks, or other Git hosts; do not mark a complete credential safety audit or production acceptance based on this scanner.

## Evidence gates
- [x] Spec and intended negative cases documented.
- [x] Scanner, tests and CI authored and persisted to PR branch.
- [ ] Disposable regression tests PASS.
- [ ] Real public repository all-ref/history audit PASS, or findings logged without secret disclosure and triaged.
- [ ] Exact-head CI verified and PR merged.
- [ ] Independent security review and full exposure inventory completed (required for L4; not claimed).

## User acceptance relationship
This security gate is orthogonal to the five feature acceptance records. Those remain **0/5 ACCEPTED** until their own independent staging/product criteria are met.
