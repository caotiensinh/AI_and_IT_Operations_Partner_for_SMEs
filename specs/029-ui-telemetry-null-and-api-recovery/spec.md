# Spec 029 — UI missing sensor and recoverable API failures (public-repo CI)

## Problem and baseline
The repository is now public (verified through GitHub API). Public visibility does not mean the five existing features are accepted: **0/5 ACCEPTED**. Current browser E2E tests tenant isolation and row equality but does not exercise real PostgreSQL NULL readings or server outage and recovery. GitHub Actions artifact quota is an independent evidence blocker.

## Before implementation: acceptance criteria
1. **AC-01: Missing telemetry.** Given authorized asset Aichi Router with a persisted PostgreSQL sample whose `cpu_percent` and `memory_percent` are SQL NULL, when Monitoring renders, the real tenant API must return JSON null and both cells must show **N/A**, never 0%; compare all rows to backend at each of 1440×900, 820×1180, 390×844 and 320×640.
2. **AC-02: Monitoring outage.** Given previously loaded Aichi telemetry, when the browser's monitoring API request is made to return HTTP 503, the UI must show an error and **zero stale telemetry rows**; when the fault is removed and the operator retries navigation, values must again match the real PostgreSQL-backed API.
3. **AC-03: Tenant switch failure.** Given active tenant A with assets, when the browser switches to tenant B and that API responds 503, the interface must not display any A or B assets as current. On recovery, the B-only assets must match tenant-B API and A's assets remain absent.
4. **AC-04: Browser evidence provenance.** Keep the 13 pre-existing Chromium screenshot outputs and SHA256/dimension validator unchanged. Failure to upload artifact is still `EVIDENCE_ARCHIVE=FAILED`, not acceptance.
5. **AC-05: Security.** No real customer data, credentials, production change or simulated success response; failure injection is **only** a browser-level HTTP 503 using Playwright, with API/backend otherwise live.

## L1–L5 rubric
- **L1:** source committed at SHA.
- **L2:** browser test and other triggered CI pass on that SHA, proving code-level behavior under disposable Postgres CI.
- **L3:** deployed staging HTTPS with real IdP, operator inspection of archived real browser outputs and restart/recovery evidenced.
- **L4:** independent operator acceptance with linked artifacts; **not claimed** by this spec.
- **L5:** production security/operations/customer gates; **not claimed**.

## Scope and dependencies
Modify only `scripts/seed_browser_e2e.py` and `frontend/tests/browser_e2e.mjs` plus this spec. Existing PRs #75, #79 and #80 and their ongoing branches are not touched. Existing 5 acceptance records are not automatically promoted by passing CI.
