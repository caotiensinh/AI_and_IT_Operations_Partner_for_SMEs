# Real-browser UI evidence capture — acceptance boundary

The Live browser PostgreSQL E2E workflow runs **real Chromium → Vite → FastAPI → PostgreSQL 16**, using **disposable synthetic data** and CI-only bearer-header authentication. It captures four viewports (1440×900, 820×1180, 390×844, 320×640) of each existing UI view: Overview, Assets and Monitoring, plus an unauthorized-state screenshot. Expected 13 PNG screenshots and one machine-readable manifest.

## Reproduce / find evidence
1. Run the `Live browser PostgreSQL E2E` workflow on a PR with the updated `frontend/tests/browser_e2e.mjs`.
2. Verify the **exact head SHA** and successful Browser cross-tenant tests in the workflow run.
3. Download the `sme-real-browser-synthetic-ci-evidence` artifact from the GitHub Actions run; `manifest.json` identifies it as a synthetic integration test, not user acceptance. Artifacts are retained for 14 days.
4. Confirm images are real browser screenshots at the stated viewport and show the relevant UI state. Do not substitute AI-generated mockups.
5. Audit API logs and negative tenant-access test in the workflow. Screenshots alone do not prove authorization.
6. Review and link immutable CI runs and separately collected real staging evidence for each acceptance criterion.

## Explicitly NOT proven
- No OIDC Authorization Code/PKCE browser sign-in in this capture workflow. Its CI-only header token is not production login proof.
- No live customer data, production server, physical monitoring device or real IdP; fake device labels are synthetic test fixtures.
- No permanent evidence: artifacts expire, so pin required approved evidence to a durable, access-controlled audit store before L4 acceptance.
- No user/operator sign-off, restart/recovery or production readiness.

Therefore **all UI acceptance ledger records remain IN_PROGRESS/L1**. Existing Chromium CI evidence can support carefully scoped L2/L3 claims after independent verification, but cannot unilaterally upgrade them.

## CI screenshot artifact quota failure

If the browser assertions PASS but `actions/upload-artifact` reports **Artifact storage quota has been hit**, CI explicitly warns `EVIDENCE_ARCHIVE=FAILED` in the job summary. The Browser job may pass its code assertions; **the screenshot evidence gate remains FALSE**. Never record screenshots as verified or advance L4/L5 on that basis.

The operator must reclaim or increase GitHub Actions artifact capacity through an authorized retention/deletion policy, rerun on the exact commit, inspect the resulting images and save required long-lived evidence in an approved store. Do not silently remove older audit evidence or invent download URLs. The negative-case and UI acceptance ledger stays `IN_PROGRESS` until actual artifacts are available and reviewed.
