# Evidence storage incident — 2026-11-22

## Observed
- CI browser run 44987615695 at SHA `585cca251ea73966bf560245489a5c4cfa57fa04` executed real Chromium + FastAPI + PostgreSQL tests and prepared **13 PNGs + manifest**.
- GitHub Actions `upload-artifact@v4` emitted `Failed to CreateArtifact: Artifact storage quota has been hit`.
- GitHub API listed **zero** artifacts for that run; consequently no screenshot acceptance evidence was retrievable.
- PR #75 run 44988947110 correctly returned CI **FAILURE** at upload, demonstrating fail-closed rather than misleading PASS.

## Remediation
1. Keep the evidence upload required; do not use `continue-on-error`.
2. Before upload, validate 13 named screenshots and matching viewport widths, fixture-only provenance, the exact 40-character source SHA, and absence of unexpected files; generate SHA256 manifest and reproducible ZIP via `scripts/package_browser_evidence.py`.
3. Retain fail-closed upload; if GitHub quota persists, run the same capture on an authorized self-hosted runner or isolated staging host and transfer the ZIP to owner-approved **durable** storage with access control and retention. This alternative is **not yet configured or tested**.
4. Verify exported ZIP with hashes and independently review screenshots before updating any `acceptance/records/UI-*.json` to L3/L4.
5. Do not delete existing GitHub artifacts or raise billing limits without explicit owner approval.

## Status and owner action
Screenshot storage remains **BLOCKED** while GitHub Actions quota is exhausted. The source code and tests can be validated independently; no screenshots are claimed as archived, nor is any UI feature customer-accepted.
