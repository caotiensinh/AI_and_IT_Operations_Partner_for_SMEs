# Source-linked requirements capture — Spec 003

## Pilot endpoint
`POST /v1/tenants/{tenant_id}/research-cases/{case_id}/requirements`

JSON:
```json
{
  "requirement_id": "client-generated-stable-UUID",
  "statement": "One concrete operational problem or requested outcome",
  "classification": "explicit",
  "source_id": "previously-registered-source-UUID"
}
```

An explicit statement MUST cite a source in the SAME case and tenant. `inferred` and `unverified` may omit source but always start in `proposed` approval status. The classification describes evidence **origin**, not a business owner's sign-off. No auto-confirmation.

Case write is allowed only if a live authenticated actor is owner/admin/manager in the tenant or site-scoped manager of the case. Application DB role can EXECUTE the narrowly scoped PostgreSQL function, but cannot write tables directly. Valid first insert returns 201; same UUID and payload replay returns 200; same UUID with altered statement/source/classification returns 409. Role and source permissions are checked before deciding whether to replay. An audit event `requirement.created` captures actor, case, requirement ID and time atomically, without storing confidential text.

## Limitations
This is metadata-only input. Original PDFs remain private and not uploaded. This implementation does not ingest source files, obtain customer consent, approve requirements, update requirements, track their versions or expose a complete Japanese operator UI. No production customer use until all trust boundaries and validation criteria are satisfied.

## Acceptance
PostgreSQL 16 CI must verify positive explicit and inferred cases, source linkage, same-key replay, conflicting reuse, viewer and forged session denial, invalid classification, cross-tenant FK and direct SQL privilege denial. Negative tests are part of the mandatory security gate.
