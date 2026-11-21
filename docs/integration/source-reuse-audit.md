# Source Reuse Audit — 2026-11-21

## Scope and evidence
Reviewed GitHub default-branch file trees and selected implementation files for ten user-owned repositories. This is a targeted source inspection, **not** an exhaustive security review or proof that old modules are production ready. Provenance: source paths and commit tree hashes below. Source projects remain independent and unchanged.

| Source (tree SHA prefix) | Inspected evidence | Proposed reusable capability | Target domain | Status |
|---|---|---|---|---|
| [Billumi](https://github.com/caotiensinh/Billumi) (b6313dfe) | `schema/0002_identity_security.sql`, `schema/0003_rls_guardrails.sql`, OCR test suite | OCR/review workflow, identity/RLS design patterns | Office AI | ADAPT, not copy |
| [workflow_office_deadline](https://github.com/caotiensinh/workflow_office_deadline) (0d202a69) | `README.md`, `rust-core/Cargo.toml`, approval tests | Deterministic Rust policy engine, approval workflow | Office AI | ADAPT |
| [ubuntu_asahi_server](https://github.com/caotiensinh/ubuntu_asahi_server) (a6bacdd1) | `control_center/README.md`, agent and monitoring tests | Metric collectors, asset monitoring and chart ideas | IT Ops | ADAPT |
| [LAN_Audio_AI](https://github.com/caotiensinh/LAN_Audio_AI) (da1fc6f0) | test tree incl. transcription/privacy tests | Meeting transcription and task extraction | Office AI | DEFER, review privacy |
| [Reverse_rea](https://github.com/caotiensinh/Reverse_rea) (d43b11df) | `pyproject.toml`, schema and camera test tree | Camera/OCR pipeline and engineering evidence records | Vision AI | ADAPT |
| [ArtCraft_Studio](https://github.com/caotiensinh/ArtCraft_Studio) (f1d9b061) | `README.md`, API and orchestration test tree | External tool orchestration principles | Platform | REFERENCE ONLY |
| [GPIO-raspberrypi](https://github.com/caotiensinh/GPIO-raspberrypi) (cc221c9c) | `rust/Cargo.toml`, hardware control tests | Rust edge protocol patterns | IoT Ops | DEFER: read-only first |
| [Mutate](https://github.com/caotiensinh/Mutate) (d6864a9e) | scoped authority grant JSON schema | Time-limited authority, approval, evidence | Platform | ADAPT |
| [AI_Web_MCP](https://github.com/caotiensinh/AI_Web_MCP) (89ab0a92) | `src/ai_web_mcp/core/redaction.py` | Error redaction, browser operator abstractions | Office AI | REFERENCE ONLY |
| [golf_ball_detect](https://github.com/caotiensinh/golf_ball_detect) (e59b3efe) | `src/golf_ball_detect/pi_agent.py`, recorder tests | Raspberry Pi camera capture/spool | Vision AI | ADAPT |
| Bear_detector | Repository lookup returned 404 | Nothing inspected | Vision AI | BLOCKED: inaccessible name |

## Source constraints
1. Old projects frequently have standalone/local identities, local SQLite stores or LAN tokens and **must not be exposed directly as shared multi-tenant services**.
2. Billumi RLS is user-scoped (`billumi.current_user_id`), not enterprise-tenant-scoped. Never port its policies directly; redesign with tenant membership, service roles, FORCE RLS and database integration tests.
3. Asahi README describes local SQLite, pinned TLS agent tokens and incomplete hardware acceptance. No claim of production-grade centralized monitoring from this inspection.
4. Golf camera agent includes a shared environment token and camera-specific system paths; must be wrapped in tenant/site/device-bound authenticated agent protocol.
5. Hardware control from GPIO must never become an unreviewed remote actuator. Initial IoT adapter read-only.
6. Source repositories lacking a root LICENSE on inspection require ownership/licensing verification before redistributing or copying code. No upstream code copied in this PR.
7. Preserve original projects, git histories and attribution. Prefer adapters, package extraction after provenance/license review, or a versioned protocol over copying entire code trees.

## Prioritized extraction
P0 (this PR): typed manifest/authorization boundary with all eight adapters **disabled by default** and seven unit tests.
P1: Billumi document OCR adapter; read-only reference and human review; isolated fixture tests.
P2: Asahi monitoring ingestion adapter with site- and device-scoped credentials.
P3: workflow_office_deadline approval engine with persisted event/audit model.
P4: Reverse_rea camera/image inference via controlled worker. Other modules later based on validated customer demand.

## Acceptance before enabling any candidate
- Permission to reuse and distribute exact files/dependencies confirmed.
- Manifest capabilities, tenant-scoped identity, resource ownership and logging policy defined.
- Positive, negative, cross-tenant and revocation tests on actual API and PostgreSQL RLS.
- Storage/object/queue isolation, retries, idempotency and secure secrets management.
- Threat model, deployment rollback and on-prem compatibility verified.
- No private dataset, credential, trained model or customer content copied without explicit authorization.
