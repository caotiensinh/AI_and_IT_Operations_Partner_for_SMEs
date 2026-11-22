# Dedicated self-hosted evidence storage — optional operating procedure

## Status
Implementation exists, but no real self-hosted runner/durable mount has yet been tested or accepted. **Not production-approved.** GitHub Actions hosted runners are ephemeral and cannot retain files by simply writing to a path.

## Prerequisites
- Trusted Linux self-hosted runner dedicated to *synthetic* test fixtures, with Playwright/Chromium, Python 3.12, Node 22, PostgreSQL 16 and a supported browser/API deployment.
- Admin-provisioned existing persistent directory (example `/srv/sme-evidence`), owned by the runner account, mounted on durable storage with restricted access, adequate free space, filesystem backups and retention policy.
- Do not pass customer data or production credentials. Do not share the raw directory publicly.

## Operator procedure
After generating the evidence directory with `SME_E2E_SCREENSHOT_DIR`, run:
```sh
python scripts/package_browser_evidence.py \
  --directory "$SME_E2E_SCREENSHOT_DIR" \
  --output /tmp/browser-evidence.zip \
  --source-sha "$COMMIT_SHA"

python -m unittest discover -s tests -p test_persist_browser_evidence.py -v

python scripts/persist_browser_evidence.py \
  --source "$SME_E2E_SCREENSHOT_DIR" \
  --root /srv/sme-evidence \
  --source-sha "$COMMIT_SHA"
```
The storage script rejects missing roots, invalid PNG/manifest/SHA, collisions, and mismatched copy hashes. Output is `/srv/sme-evidence/<sha>/` with 13 PNGs, manifest and SHA256SUMS. Treat any failure as evidence BLOCKED.

Independently inspect files, verify checksums, record storage owner and a durable access-controlled reference, then ask an independent reviewer to compare observed UI with acceptance criteria. Never call L4 from storage success alone.

## Limits
This implementation does not configure a self-hosted runner, mount storage, run Chromium there, provide backup, or obtain independent human sign-off. The existing GitHub workflow intentionally stays FAIL while its mandatory Actions artifact upload cannot be completed. Do not silently replace GitHub evidence with an unverified local path.
