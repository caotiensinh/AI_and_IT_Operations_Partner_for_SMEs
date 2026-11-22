# Spec 028 — Browser UI ↔ API comparison oracle (CI synthetic fixture)

## Baseline
Existing five acceptance records: 0/5 ACCEPTED. Real Chromium screenshot capture integrity was proven in Spec 027 but GitHub Actions upload was blocked by artifact storage quota. An image does not independently prove that displayed values came from the tenant-authorized backend.

## Expected vs actual acceptance contract
- **AC-01: Overview.** Given an authorized tenant with N assets, when Overview loads or changes company, the visible asset count must equal the independently fetched `GET /v1/tenants/{tenant}/assets` result, and names/site IDs/asset IDs must match all returned rows. Foreign tenant assets must be absent.
- **AC-02: Assets.** On each of four viewport sizes, every browser table row must equal the tenant-scoped API asset name, site ID and asset ID in the same order; wrong row count or mismatch causes CI failure.
- **AC-03: Monitoring.** On each viewport, every browser telemetry hostname, CPU, memory and sample timestamp must equal the authorized `GET /v1/tenants/{tenant}/itops/asahi/latest` response. Both tenant A and tenant B are exercised, and cross-tenant carryover must be absent.
- **AC-04: Authorization.** A login valid only for tenant A must receive 403 for both tenant B assets **and** tenant B telemetry. No-browser-token state must show an error and no data.
- **AC-05: Evidence boundaries.** Retain 13 Chromium PNG captures with verified viewport dimensions and SHA256 in a synthetic CI manifest. Upload may fail due to external quota; never promote these checks into human UI acceptance or production.

## Implementation scope
Only the Playwright integration test and Spec Kit. No staging data, backend API contracts, authentication logic, UI styling, deployment or production configuration is modified. All tests are positive or negative assertions using the existing independently authorized API.

## Verification
- [x] Contract defined and comparison assertions committed
- [ ] Browser CI confirms API field shape and exact equality at all four viewports
- [ ] Other triggered checks pass on final HEAD
- [ ] Screenshot archival succeeds and operator reviews (separate external prerequisite)
- [ ] User signs L4 for Overview/Assets/Monitoring on real deployed staging (separate external prerequisite)

Even a green CI PR means **L2 component/integration-test verification only**; five acceptance records remain IN_PROGRESS until independent review, real staging and evidence archive.
