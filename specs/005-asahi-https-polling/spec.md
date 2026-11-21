# Spec 005 — Read-only Asahi HTTPS poll adapter

## Context
The existing `ubuntu_asahi_server` agent exposes
`GET /api/agent/status` via HTTPS with Bearer authentication.
This adapter reuses the actual source contract without copying engine code.

## Scope
- Trust an **administratively configured** fixed HTTPS status URL, CA trust
  root, agent token and server-side tenant/site/device binding.
- Require TLS peer verification with a configured CA; never use verify=False.
- Disable redirect following and environment HTTP proxy trust.
- Bound timeout, response body size and JSON schema.
- Normalize the response through Spec 004's typed Asahi adapter.
- Preserve NA/null for unsupported sensors.
- Test malicious/invalid URLs, unauthorized responses, stale samples, payload
  metadata spoofing and response overflow without live hardware.

## Non-goals
No public API for agent registration or arbitrary URL submission; no live
device contact, token provisioning, poll scheduler, persistence, replay database,
alerting or production status.

## Acceptance
Positive and negative unit tests PASS in GitHub Actions. All existing
PostgreSQL, staging and Chromium checks remain PASS. No customer secret
or endpoint is committed.
