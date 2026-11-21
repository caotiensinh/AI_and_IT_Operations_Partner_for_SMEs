# Spec 006 tasks
- [x] Define isolated database role and trusted enrollment schema
- [x] Implement validated single-write function with replay/duplicate rejection
- [x] Implement restricted worker call using existing read-only TLS poller
- [x] Run 184 PostgreSQL tests on PR #32 and 187 on PR #34, including negative isolation cases
- [x] Verify five PR #32 workflows PASS and merge #32; PR #34 PostgreSQL CI PASS and merged
- [ ] Provision secret manager and rotate pilot credentials
- [ ] Run on a real agent with verified TLS and two-site negative tests
