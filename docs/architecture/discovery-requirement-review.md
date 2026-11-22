# Spec 003 — Evidence review decisions and optimistic concurrency

## Scope
This is a **research evidence review**, not a customer purchase order, project sign-off or authorization to change a production system. Research records begin as `proposed`. A tenant/site manager or tenant owner/admin can accept an explicitly source-linked statement as `confirmed`, or mark an explicit/inferred/unverified statement `rejected` with a rationale.

POST `/v1/tenants/{tenant_id}/research-cases/{case_id}/requirements/{requirement_id}/review`

Request: `{"expected_version":0,"decision":"confirmed","rationale":"Reviewed original project brief"}`

Successful first decision returns state, incremented `review_version` and `updated:true`. Same decision and current expected version returns `updated:false` with no new event. A stale `expected_version` returns 409; an illegal transition (inferred->confirmed, rejected->confirmed, confirmed->rejected, empty rationale) returns 422; unauthorized actor or out-of-scope resource returns 403. The endpoint must never treat a classification label as proof of explicit business authorization.

## Database authorization
Migration 0010 adds `review_version`, a tenant-scoped append-only `discovery_requirement_reviews` history and a transactionally written `requirement.reviewed` event. A limited SECURITY DEFINER function:
1. checks active, unrevoked session + tenant membership;
2. checks case site and owner/admin/manager role;
3. locks requirement row with `FOR UPDATE` before comparing expected version;
4. refuses confirmation unless classification is `explicit` with a source UUID;
5. changes only approval_state/review_version and atomically inserts decision history + audit.

The runtime DB role `sme_app` cannot directly update requirements or read reviewer history. There is no general UPDATE, no bypass for a viewer or another tenant, no ability to reverse terminal decisions. A separate revision workflow would require a new spec, snapshots and evidence.

## Acceptance gate
Real PostgreSQL integration tests must cover explicit confirmation, inferred confirmation refusal, inferred rejection, stale-version conflicts, final-state immutability, no-op replay, viewer denial, foreign tenant denial and direct DB mutation failure. This work is a backend-only research pilot and is **not** released to customers.

## Remaining capabilities
- No decision history GET endpoint for managers or sanitized exports;
- No requirements versioning/editing, approval delegation, formal dual control or signature;
- No browser UI, safe PDF uploads, tenant contract consent or production rate limits;
- No real customer review or operational rollout.
