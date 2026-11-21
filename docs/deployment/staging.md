# Staging Compose — local engineering profile (not production)

## Purpose
Provide a reproducible multi-container baseline: PostgreSQL 16; migration job; separate
non-superuser `sme_runtime` DB login that can assume only `sme_app`; Python
FastAPI; built React static UI behind nginx. Host port is **loopback-only HTTP**.
The identity-provider browser flow is NOT wired; login is intentionally unavailable.

## Quickstart (isolated lab only)
1. Copy `.env.staging.example` to `.env.staging`.
2. Replace both passwords with *different*, random 32+ byte credentials.
3. `docker compose --env-file .env.staging -f compose.staging.yml config --quiet`.
4. `docker compose --env-file .env.staging -f compose.staging.yml up -d --build`.
5. `sh scripts/staging_smoke.sh`. Expected: UI 200; anonymous API 401.
6. `docker compose --env-file .env.staging -f compose.staging.yml down`.

## Security boundary
- The migration job holds elevated database credentials for one-off schema work.
- API service uses only `sme_runtime`, **not postgres**. No DB port published.
- Nginx reverse proxies only /v1, not privileged auth/bootstrap endpoints.
- No customer accounts, bearer secrets or seed data; UI shows login error until a
  real OIDC provider and cookie backend are fully integrated.
- No TLS, external exposure, complete session lifecycle, real login, high availability,
  backup/restore, object store or Rust agent in this profile.
- Do not re-use passwords from this configuration or expose port through remote tunnels.
- Volume is persistent across `down`; `down -v` destroys staging data and is CI only.

## Acceptance and evidence
Workflow `.github/workflows/staging-compose.yml` validates Compose, builds images,
runs migrations and smoke checks unauthenticated routes, and proves runtime role
cannot read session secrets or write membership. This is a **deployment smoke**,
not production security certification.

## Next phases
Implement real HTTPS/OIDC provider callback, auth-role split, object storage,
secret manager, backup+restore drill, and tenant-aware Asahi metrics adapter.

See [disposable recovery drill](recovery.md) for a basic SQL restore test.
