# Evidence source metadata intake — Spec 003, source traceability

## Endpoint
`POST /v1/tenants/{tenant_id}/research-cases/{case_id}/sources`

JSON: `{"source_id":"<client-generated UUID>","document_label":"Synthetic interview notes","page":1}`. Use one stable UUID per logical source metadata record and retain it over network retries.

First creation: 201 with source ID and `replayed:false`. Identical retry: 200, same UUID, `replayed:true`. Same UUID with different case, label or page: 409. Unauthorized or out-of-scope case: 403. Source documents **are not uploaded**; only label and page are stored.

## Security boundary
The database `sme.create_discovery_source_once` runs as the limited NOLOGIN `sme_discovery_service` definer. It independently verifies live session and tenant, checks an existing research case and an applicable owner/admin/manager assignment, and only then inserts source metadata. A site manager cannot create sources for another site, and viewer/operator have no write permission. App `sme_app` cannot INSERT directly.

The primary-key conflict implements idempotent retries, and the create event is committed atomically. Audit `source.created` records tenant, actor, case, source UUID and timestamp, not source file contents. No update/delete capability is exposed.

## Not yet implemented
- No PDF upload/extraction, customer consent collection, document encryption, virus scan, retention policy or production browser authentication.
- No requirement creation endpoint: source metadata is groundwork for explicit source-backed statements.
- No global source deduplication or version history; UUID identifies one logical source, not content hash.
- Real enterprise data cannot be used until approved intake and compliance gates exist.
