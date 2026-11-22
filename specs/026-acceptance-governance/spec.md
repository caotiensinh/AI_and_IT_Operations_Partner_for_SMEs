# Spec 026 — Acceptance-first delivery governance

## Scope
Define one unambiguous, testable, auditable completion contract for the SME platform and implement automated structural validation. Prevent reporting CI PASS or merged PRs as product completion.

## Outcomes
- One status vocabulary and L0–L5 maturity definitions.
- Explicit evidence checklist: persisted SHA, positive/negative tests, live integrated UI/API/DB, security, rollback, human acceptance.
- A machine-readable acceptance record schema, validator and negative regression tests.
- PR checklist and CI contract checking; no automatic approval or release claims.
- Existing tasks and services are **not** retroactively ACCEPTED.

## Acceptance criteria
- Given an incomplete task, when it is checked, then schema validation can PASS but '--require-accepted' fails.
- Given a forged ACCEPTED claim lacking evidence, when checked, it fails closed.
- Given an independent reviewer signing a different SHA/environment or themselves, acceptance fails.
- Given all required gates, linked evidence and an independent review on exact SHA/environment, a scoped record may report ACCEPTED.
- No production deployment is created or authorized.

## Dependencies and exclusions
Existing Constitution v1 and Spec Kit; Spec 024 remains a separate draft PR. This contract does not change production endpoints, credentials, permissions, or prove old work completed. Human evidence assessment cannot be automated by a JSON validator.
