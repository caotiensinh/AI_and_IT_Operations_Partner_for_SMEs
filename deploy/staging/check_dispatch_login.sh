#!/bin/sh
set -eu
: "${SME_DISPATCH_DB_PASSWORD:?missing dispatcher password}"
export PGPASSWORD="$SME_DISPATCH_DB_PASSWORD"
db="psql -X -v ON_ERROR_STOP=1 -h db -U sme_dispatch_runtime -d sme"
[ "$($db -At -c 'SELECT session_user')" = sme_dispatch_runtime ]
[ "$($db -At -c 'SET ROLE sme_dispatch; SELECT current_user' | tail -n 1)" = sme_dispatch ]
for role in sme_app sme_auth sme_ingest; do
  if $db -c "SET ROLE $role" > /tmp/dispatch-role-denial.log 2>&1; then
    echo "Unexpected cross-role escalation"; exit 1
  fi
  grep -q 'permission denied' /tmp/dispatch-role-denial.log
done
if $db -c 'SELECT * FROM sme.asahi_alert_outbox' >/tmp/dispatch-read-denial.log 2>&1; then
  echo "Unexpected raw queue read"; exit 1
fi
grep -q 'permission denied' /tmp/dispatch-read-denial.log
if $db -c 'UPDATE sme.asahi_alert_outbox SET delivery_attempts=0' >/tmp/dispatch-write-denial.log 2>&1; then
  echo "Unexpected raw queue write"; exit 1
fi
grep -q 'permission denied' /tmp/dispatch-write-denial.log
echo "PASS: dispatcher login isolated from app/auth/ingest and queue DML"
