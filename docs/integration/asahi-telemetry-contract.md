# Asahi read-only monitoring adapter — contract increment

## Source evidence (audited 2026-11-21)
- `caotiensinh/ubuntu_asahi_server/agent/asahi_agent.py`, tree a6bacdd1.
- `caotiensinh/ubuntu_asahi_server/control_center/agent.py`.
- `control_center/README.md`: stand-alone LAN monitoring design, HTTPS pinned fingerprint/token, and known incomplete real-node acceptance.
- Root `LICENSE` was not found; **no upstream code has been copied**.

## Delivered
Pure Python adapter normalizes ASAHI's existing snapshot schemas to a narrow, typed,
tenant/site/device-scoped telemetry envelope. Hostname is descriptive, never identity.
Payload-supplied tenant/site IDs are discarded. Rejects missing timestamps,
future/stale samples, invalid percentages, malformed disks and unknown bindings.
Unknown payload fields (e.g., IP addresses, secrets, process details) are not persisted
by the contract. Null means sensor unavailable, not 0.

## Important release gates
- This is ONLY a normalization boundary, not a production agent integration.
- No network polling, TLS fingerprint validation, mTLS enrollment, remote agent registration,
  PostgreSQL metrics storage, history, alerts, dashboards or actual hardware A/B tested yet.
- The service must derive binding from a trusted tenant/device enrollment lookup,
  not incoming JSON/hostname.
- Multi-tenant ingest and persistence require unique (tenant,site,device), idempotency,
  bounded rate, replay protection, encrypted secrets and cross-tenant negative E2E.
- Keep all candidate adapters in the registry disabled until those tests PASS.
