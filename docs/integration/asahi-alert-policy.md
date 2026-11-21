# Alert evaluation slice: not live notification delivery

`AsahiAlertEvaluator` receives a trusted, normalized sample and returns
zero or more `AlertDecision` transition records. It is deliberately side-effect
free apart from a bounded in-process state cache. Decisions are NOT saved and
NOT sent to customers.

Default policy: CPU/RAM >=90% for two distinct chronological samples;
clear only at or below 80%. Missing values are ignored. Per-tenant/site/device
metric state isolates alert transitions. No real agent, scheduler loop,
notification provider, persistent incident or on-call workflow is activated.

Before production: persist alert state and decisions transactionally, add
idempotent outbox, multi-worker locking, retention, customer-specific
thresholds and clear incident ownership; verify a real high-load test.
