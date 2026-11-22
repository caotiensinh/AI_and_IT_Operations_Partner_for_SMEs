# Spec 014 — Supervised worker service loop

## Goal
Implement a testable, fail-closed, interruptible loop around the existing
single leased worker tick. It must not invent agent enrollment or credentials.

## Acceptance
- Interval and retry delays are bounded and independently configurable.
- Stop event interrupts sleep and terminates without calling the tick again.
- Valid outcomes are strictly limited to not_due, inserted and duplicate.
- Retry only known transient exceptions; unexpected auth/config failures
  propagate as hard errors to the process supervisor.
- Bounded consecutive failures result in FAILED state.
- Structured status snapshots reveal only count/state/outcome, not secrets,
  endpoint URL, payload or exception text.
- Reentrant invocation is rejected. Regression tests and CI green.

## Non-goals
This component is not a deployed daemon, not connected to a real agent, and
does not fetch or inject live credentials. External process supervision,
configuration loading, secret management, multi-enrollment scheduling, TLS
pilot, monitoring endpoint, and signal handling remain separate milestones.
