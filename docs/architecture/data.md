# Storage and Database Architecture

## Data categories
| Type | Store | Partition strategy |
|---|---|---|
| Tenant, identity membership, configuration | PostgreSQL | Tenant-scoped rows + RLS |
| Workflows, tickets, inventory, approvals | PostgreSQL | tenant_id + indexes; partition high-volume by tenant/time if needed |
| Files, OCR originals, images, video clips | S3-compatible object storage | tenant-specific prefix/bucket/policy; never relational BLOBs |
| Device telemetry, measurements | PostgreSQL initially | append-only time partitions; add TimescaleDB-compatible option only after license/capacity review |
| Events, jobs, audit | PostgreSQL outbox and durable append-only audit sink | Tenant-scoped, immutable semantics and retention |
| Cache/session throttle | Redis/Valkey optional | tenant-scoped cache keys; never system of record |
| Search and embeddings | PostgreSQL FTS/pgvector if required | strict tenant filter with tested RLS; separate indexes for high-assurance isolation |

## Initial schema candidates
tenants(id, slug, name, status, deployment_profile, created_at)
identities(id, oidc_subject, email_hash, status)
memberships(id, tenant_id, identity_id, status, joined_at)
sites(id, tenant_id, name, timezone)
departments(id, tenant_id, site_id, parent_department_id, name)
role_assignments(id, tenant_id, membership_id, role, scope_type, scope_id)
assets(id, tenant_id, site_id, type, external_ref)
jobs(id, tenant_id, principal_id, idempotency_key, state, payload_ref)
objects(id, tenant_id, bucket, key, checksum, retention_until, classification)
audit_events(id, tenant_id, actor_id, action, target_id, occurred_at, correlation_id)
outbox_events(id, tenant_id, event_type, payload, delivered_at)

Use UUID identifiers, UTC timestamps (render local tenant timezone), optimistic locking where needed, restrictive foreign keys, schema migrations, constraints and tested deletion strategies.

## Backup/restore
A database snapshot alone is not enough. Persist DB dump/base backups, object store versioned snapshot and encryption key references to a coordinated recovery point. Restore drill must verify object references and tenant audit continuity.
