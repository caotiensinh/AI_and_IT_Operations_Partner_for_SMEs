# Spec 024 — Production readiness gate (non-deploying)

## Problem
Spec 023 explicitly leaves real IdP, HTTPS, distributed throttling, isolated production principals, security review, and operational validation incomplete. Passing CI alone is not permission to deploy.

## L1 / L2 / L3
- **L1 Owner:** understands release readiness and evidence links, never sees a synthetic test represented as production acceptance.
- **L2 Release pipeline:** validates the schema of `release/readiness.json` in CI; production delivery jobs must execute `python scripts/check_release_readiness.py --check-production` and stop on nonzero status. No deployment job is added here.
- **L3 Controls:** strict required controls, evidence links for every positive check, deny-by-default, status derived from all controls. JSON file is only an attestation index, not itself proof of real-world security; reviewers must validate evidence and current provider/environment.

## Acceptance
- [x] All eight gates start blocked; production check exits 1.
- [x] Invalid or incomplete manifests fail closed (exit 2); positive claims require HTTPS evidence links.
- [x] Schema validation may PASS while production remains BLOCKED.
- [x] Regression suite covers positive, negative, malformed, and CLI paths.
- [ ] Independent reviewer validates real-world evidence and environment.
- [ ] Production deploy pipeline invokes --check-production before any deployment, when a production deploy pipeline exists.
- [ ] Actual IdP, TLS, rate limits, role secrets, backup drill, observability and tenant acceptance gates are completed.

## Important limitation
This is NOT a deployment, external verification, authorization to merge staging PR #67, or an assertion that evidence links are trustworthy. A user-controlled manifest could be falsified: protect main and require independent approval and branch checks before treating it as an authorization artifact.
