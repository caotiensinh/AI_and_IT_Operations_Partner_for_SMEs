# Spec 027 — Browser evidence integrity gate (synthetic CI only)

## Prerequisite and objective
The immutable acceptance baseline starts at **0/5 ACCEPTED**. Browser CI can successfully test Overview, Assets and Monitoring while GitHub Actions refuses all artifacts due to storage quota. Do not claim screenshot acceptance merely because the UI test or build passes. Provide a deterministic, testable integrity gate independent of archival.

## Scope and acceptance
1. Given a headless real Chromium render at the four defined viewports (1440×900, 820×1180, 390×844, 320×640), when 3 UI views and 1 unauthorized case are captured, then exactly 13 PNG files exist, each with the expected *viewport* pixel dimensions, minimum length, and SHA256 digest in the manifest.
2. Given the manifest and exact Git commit SHA, when the validator executes, then every file name is whitelisted, the digest/size/dimensions match, the manifest is explicitly synthetic and UNREVIEWED, and unexpected/missing files cause CI failure.
3. Given screenshot archival is blocked by quota, when the browser assertions and integrity validator pass, then CI may report `CAPTURE_INTEGRITY=PASS` **but must separately report** `EVIDENCE_ARCHIVE=FAILED` and never advance an acceptance record.
4. Given forged acceptance status, changed bytes, wrong SHA, wrong image dimensions, missing screenshot or unexpected file, the verifier exits nonzero.
5. No public deployment, OAuth login, customer data, screenshot approval or production acceptance is claimed.

## L1–L3 boundaries
- **L1:** screenshot generation logic and stable manifest persisted in Git.
- **L2:** CI screenshot integrity and negative validator tests pass on exact commit.
- **L3:** requires *archived* real browser captures + external reviewer of staging evidence. Synthetic CI screenshots alone do not prove real authenticated IdP or enterprise deployment.
- **L4/L5:** independent owner acceptance and full production gates are still missing.

## Dependencies and isolation
Reuse existing browser Playwright script and `acceptance/records/UI-*.json` unchanged. Do not touch stacked Discovery PRs. Existing artifact upload remains best-effort because GitHub Actions storage quota is an external capacity constraint, explicitly reported separately from test success. This change does not solve that quota.

## Evidence log
Record PR checks, exact SHA, rendered screenshot count and archival result. When artifact upload fails, **do not fabricate screenshot links** or move UI acceptance beyond `IN_PROGRESS`.
