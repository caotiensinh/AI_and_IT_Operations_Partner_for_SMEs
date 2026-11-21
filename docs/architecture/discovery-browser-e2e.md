# Discovery Workspace: real browser E2E gate

## What is actually verified

The `Discovery Real Browser E2E` GitHub Actions workflow provisions PostgreSQL 16 in a disposable service container, applies migrations 0001–0011, creates synthetic tenant/site/manager/session data in `sme_test`, runs the actual FastAPI application on the runner's loopback, and launches Chromium via Playwright against Vite's same-origin development proxy.

The browser exercises:
1. Tenant and opaque test-session authentication.
2. Create a research case in real PostgreSQL.
3. Add source reference metadata only (no file bytes).
4. Create an explicitly evidenced requirement.
5. Review and confirm with rationale; fetch and display immutable review history.
6. Reject an invalid bearer session without entering the workspace.

There are no mocked browser API responses. The test session fixture is random, generated only in CI with file permission 0600, not printed or committed. The API refuses to run outside `SME_E2E_ONLY=1` and a loopback PostgreSQL connection to the disposable `sme_test` database.

## Developer reproduction

Use a disposable local PostgreSQL 16 database called `sme_test`, username/password controlled by the tester; do not point these commands at company/customer infrastructure. Install Python 3.12 and Node 22.

```sh
export SME_TEST_DATABASE_DSN=postgresql://postgres:postgres@127.0.0.1:5432/sme_test
export SME_E2E_ONLY=1
export SME_E2E_FIXTURE_PATH=/tmp/sme-discovery-e2e-session.json
export DISCOVERY_API_ORIGIN=http://127.0.0.1:8000
python -m pip install -e . 'psycopg[binary]>=3.2,<4' 'uvicorn>=0.30,<1'
python scripts/discovery_e2e_seed.py
python scripts/discovery_e2e_server.py &
cd web/discovery
npm install --no-audit --no-fund
npx playwright install --with-deps chromium
npm run test:e2e
```

The test setup refuses to overwrite the bearer fixture and does not clean up the database; drop the disposable test database after completion. CI deletes its ephemeral fixture and stops the loopback API even on failure.

## Boundaries and acceptance

This verifies Chromium browser + real API + real PostgreSQL in one CI environment, not a production deployment. It does not prove OIDC/PKCE login, HTTPS, secure cookies, anti-CSRF, multi-device access, DNS/routing, performance under load, accessibility compliance, production backup/restore, or a real customer pilot. It does not upload or parse confidential original customer documents.

Do not mark end-to-end acceptance PASS until the **final implementation SHA** has green Playwright and frontend unit/build workflows with log evidence. Re-running the same failing commands without new evidence is prohibited.
