# Spec 003 — Review decision history visibility

## API contract
`GET /v1/tenants/{tenant_id}/research-cases/{case_id}/requirements/{requirement_id}/reviews`

Returns current `approval_state`, `review_version` and ordered `reviews` with `version`, `previous_state`, `next_state`, `rationale`, `reviewer_id` and `reviewed_at`. An eligible requirement with no reviews returns an empty list and version zero.

## Trust boundary
PostgreSQL `sme.get_discovery_requirement_review_history` resolves an active opaque session and membership, checks case scope and restricts to tenant owner/admin/manager or site manager. The function runs as the existing NOLOGIN security definer; it reads review history only after authorization, using tenant RLS. A viewer/operator, another tenant or missing item does not receive review notes. Runtime `sme_app` does not gain direct SELECT on private review rows.

Decision history is **research review evidence**, not proof of customer contractual acceptance, production change authorization or legal sign-off.

## Current boundaries
Review decisions are terminal; at most one non-no-op decision is currently allowed for each requirement. Pagination will be necessary before multi-round reviews, revised requirements or richer audit features are introduced. No UI, export, dual-control or customer consent workflow is shipped here. Original private PDFs stay outside repository and service.

## Acceptance
Real PostgreSQL 16 tests check manager-visible history and source-linked version, empty-history response, private reasons denied to viewer/cross-tenant, unknown requirement denial and app-role inability to read the history table.
