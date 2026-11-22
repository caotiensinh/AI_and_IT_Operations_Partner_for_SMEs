# Definition of Done — mandatory acceptance contract (v1.0)

This document governs every task, feature, UI screen, module, integration and release. It does not retroactively certify existing work.

## Status dictionary (exactly one per acceptance record)

| Status | Meaning | Allowed reporting |
|---|---|---|
| NOT_STARTED | No persisted implementation evidence | Not started |
| IN_PROGRESS | Work exists but any acceptance gate is unproven | In progress; explicitly list what is missing |
| BLOCKED | External prerequisite prevents acceptance | Blocked; name dependency and unblock condition |
| READY_FOR_REVIEW | All objective gates evidenced, awaiting independent sign-off | Implementation tested; NOT complete |
| REJECTED | Reviewer rejected evidence or behavior | Not accepted |
| ACCEPTED | All required gates evidenced **and** independent human reviewer signed the same commit and environment | Completed for the explicitly named scope only |

**Never call NOT_STARTED, IN_PROGRESS, BLOCKED, READY_FOR_REVIEW or REJECTED "done", "PASS", "100%", "released", or "production-ready".** A unit test PASS, pull request merge, green CI, screenshot mock, unverified URL, drafted spec or demo is not feature acceptance.

## Required scoped acceptance gates

1. **Contract:** task ID, owner, scope, exclusions, upstream dependencies, testable Given/When/Then criteria and expected negative cases are written *before implementation*. Existing work must be inventoried without claiming retroactive completion.
2. **Persist:** implementation exists on a pinned remote Git commit; docs/contract updated and durable.
3. **Functional:** positive, negative, boundary, failure/recovery and regression paths executed; evidence includes exact inputs, expected/actual results and test environment. Unsupported categories must be explicitly justified and signed by reviewer; not silently skipped.
4. **Security:** tenant boundary, role authorization, secrets/logging and unsafe-input paths tested when applicable. Security-relevant changes require negative cross-tenant tests.
5. **Integration:** dependencies and the complete user workflow tested end-to-end with actual services/data in an isolated environment, not only mocks. Screens need real browser screenshots with viewport and SHA; recordings/screenshots alone cannot prove backend behavior.
6. **Operations:** clean deployment and restart, rollback/recovery, observability and error handling demonstrated for deployable changes. Staging acceptance does not imply production acceptance.
7. **Evidence:** link to immutable run artifacts/logs, actual UI captures, test commands, configuration, version/SHA, timestamps and scope. Distinguish synthetic IdP, staging seed and actual real-world devices.
8. **Review:** an independent human reviewer (not the author) checks failures and evidence, records an explicit decision tied to exact SHA and environment.
9. **Product acceptance:** the user can launch, log in, complete the agreed task, inspect resulting persistent state, and repeat it after restart. For customer pilot/production, tenant owner acceptance and real IdP/TLS/monitoring/backup must be separately proven.

## Hierarchy: never promote evidence between levels

- **L0 Planned:** requirement/spec only. No implementation credit.
- **L1 Implemented:** committed code; not automatically tested.
- **L2 Verified component:** automated positive/negative tests PASS at the exact SHA.
- **L3 Integrated staging:** real browser/API/database/agent E2E in deployed staging, including failure paths and captures.
- **L4 User-accepted:** independent review plus operator completes the intended workflow and signs the exact environment/SHA.
- **L5 Production accepted:** L4 plus authorized deployment, production controls, monitoring, recovery drill and customer sign-off.

**Definition of COMPLETE for an ordinary feature: L4 / ACCEPTED.** L2 means "component verified"; L3 means "staging integrated". A production release additionally requires L5.

## Evidence format and governance

Store machine-readable decisions under `acceptance/records/<task-id>.json` according to `acceptance/schema-example.json`. CLI `python scripts/check_acceptance.py` checks all records, rejects inconsistent claims and reports incomplete items. `--require-accepted` exits nonzero unless all records are ACCEPTED. Contract-validation CI passing means only that reports are structurally consistent, NOT that all items have passed product acceptance.

For every status update, publish: **Completed** (ACCEPTED IDs only), **Remaining** (non-ACCEPTED IDs), **This-session improvement** (number of newly ACCEPTED IDs with verified evidence), and **Blockers**. Denominator must be stable over the same scope/version; don't use arbitrary percentage estimates.

## Change control

Requirements/criteria may change only through reviewed versioned spec change before implementation is accepted. An acceptance signed for one SHA/environment becomes stale when behavior-affecting code changes; re-test and re-approve. Never auto-sign acceptance from a bot. Existing merged PRs retain their historical CI results but start as unreviewed in this new ledger.

## Phase gate for further development

No further speculative feature-expansion claims until the three existing UI screens (Overview, Assets, Monitoring) are run from the real app, authenticated, captured at desktop and mobile sizes, and verified against real authorized backend responses in staging. Failed/missing evidence must be reported as incomplete, never fabricated.
