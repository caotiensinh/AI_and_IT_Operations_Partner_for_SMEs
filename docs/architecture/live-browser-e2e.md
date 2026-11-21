# CI live browser E2E slice

Tests four Chromium viewport sizes (1440, 820, 390, 320 px) using the real React workspace, Vite's local /v1 proxy, FastAPI and disposable PostgreSQL 16. Checks tenant switching, only authorized assets visible, no 320px horizontal overflow, unauthorized session and forbidden cross-tenant request.

The harness runs only with SME_E2E_FIXTURE_MODE=disposable_ci_only, binds loopback, refuses nonlocal database hosts and seeds no real accounts. Random fixture tokens live in a chmod 0600 runner-only file and are never logged.

**Important boundaries:** browser tests inject a bearer header to exercise the real application API, but do not exercise the cookie/OIDC browser login itself. The browser authentication flow, production non-superuser DB roles, TLS, CSP, strict secrets and provider integration remain separate release gates. Vite dev server is NEVER a production deployment.
