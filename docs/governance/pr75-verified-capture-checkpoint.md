# PR #75 — Independent synthetic screenshot verification (2026-11-23)

## Verified artifact
- GitHub Actions run: https://github.com/caotiensinh/AI_and_IT_Operations_Partner_for_SMEs/actions/runs/45181886100
- Artifact ID: `14820598458` (`sme-real-browser-synthetic-ci-evidence`), non-expired at review time.
- Source commit: `79c5c9a0abdfb7665e555f9f753a9e821c4f412c`.
- Original artifact ZIP size: 1,203,903 bytes.
- Manifest classification: `INTEGRATION_TEST_NOT_USER_ACCEPTANCE`, `synthetic_data=true`, `production_ready=false`, `acceptance_status=UNREVIEWED`.
- Independent inspection of **all 13 PNGs**: each file's SHA256, byte count, actual PNG IHDR width and height matched `browser/manifest.json`.
- Independently inspected the second ZIP (`browser-evidence.zip`) nested in the artifact: all 13 image payloads and recorded SHA256 values matched the outer archive; manifest SHA256 matched too.
- Original content was downloaded and inspected via GitHub connector, not recreated from CSS or test expectations.

## Review result
- PNG capture and archive integrity: **PASS (13/13)**.
- GitHub artifact storage: **CONFIRMED** for the exact run and ID above.
- Browser CI: **PASS** on the exact source commit; the runtime uses synthetic authorization and disposable fixtures.
- Human independent approval: **MISSING**; staging HTTPS, real OIDC and production restart/restore acceptance remain **NOT TESTED**.
- Consequently UI-OVERVIEW, UI-ASSETS and UI-MONITORING remain **IN_PROGRESS**, not L4 `ACCEPTED`.
- This verification is only a point-in-time attestation; GitHub artifact retention is limited and does **not** replace a long-term immutable owner-controlled archive.

## Reproducibility
Download GitHub Actions artifact `14820598458`, inspect `browser/manifest.json`, independently recompute SHA256 and PNG dimensions for all 13 `browser/*.png`, and cross-check the nested `browser-evidence.zip` + `sha256sums.json`. Record exact source SHA, reviewer, and storage provenance before any acceptance claim.
