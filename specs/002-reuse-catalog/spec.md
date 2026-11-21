# Spec 002 — Reuse Existing Project Capabilities

## User story
As an SME platform integrator, I can register a capability implemented in a separately maintained user-owned repository without weakening tenant isolation or importing its old authentication and persistence assumptions.

## Design
Capability adapters are initially catalog entries only. Every manifest is disabled. A future runtime supplies a verified principal, selected tenant from server membership, authorized resource ownership and capability allowlist. Domain adapter accepts AuthorizedInvocation; worker independently checks resource tenant, RLS and device/site scope. Never trust browser-supplied tenant IDs.

## Acceptance implemented in first increment
- [x] Eight adapter candidates described using typed Python manifests.
- [x] Deny-by-default access control on initial registry.
- [x] Seven deterministic unit tests: valid authorized invocation, cross-tenant denial, unknown adapter denial, ungranted capability denial, disabled-by-default, duplicate registration rejected, empty grants denied.
- [x] Targeted source audit with provenance and extraction priorities.
- [ ] PostgreSQL RLS and database-backed memberships.
- [ ] Actual OCR or monitoring integration.
- [ ] Rust edge component implementation.
- [ ] Real tenant A/B API end-to-end test.
- [ ] Verified deployment and rollback.

## Commands
```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Security limitations
The first Python guard is **not** production authorization: caller supplies a Principal object. Trusted session/OIDC validation, membership lookup, resource ownership checks, RLS, and external adapter execution are not implemented. The registry cannot execute any source-project action by design.

## Next steps
1. Implement real tenant tables and enforced RLS on PostgreSQL, then trusted OIDC/membership context.
2. Define a versioned `DocumentExtractionRequest/Result` contract with human-review and audit.
3. Extract Billumi OCR under an isolated Python worker without importing its user database/auth tables.
4. Add evidence-based integration tests and only then enable `billumi-ocr` for a test tenant.
