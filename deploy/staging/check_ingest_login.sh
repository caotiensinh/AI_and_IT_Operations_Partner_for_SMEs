#!/bin/sh
# Staging CI only. Verify actual password-authenticated PostgreSQL login.
set -eu
: "${SME_INGEST_DB_PASSWORD:?ingest credential missing}"
export PGPASSWORD="$SME_INGEST_DB_PASSWORD"
db="psql -X -v ON_ERROR_STOP=1 -h db -U sme_ingest_runtime -d sme"
login=$($db -At -c 'SELECT session_user')
[ "$login" = sme_ingest_runtime ] || { echo "Wrong database principal"; exit 1; }
role=$($db -At -c 'SET ROLE sme_ingest; SELECT current_user')
[ "$role" = sme_ingest ] || { echo "Cannot assume ingest role"; exit 1; }
if $db -c 'SET ROLE sme_app' >/tmp/app-role-check.log 2>&1; then
  echo "Unexpected SME application privileges"; exit 1
fi
grep -q 'permission denied' /tmp/app-role-check.log
if $db -c 'SET ROLE sme_auth' >/tmp/auth-role-check.log 2>&1; then
  echo "Unexpected SME authentication privileges"; exit 1
fi
grep -q 'permission denied' /tmp/auth-role-check.log
if $db -c 'SELECT credential_digest FROM sme.asahi_enrollments' >/tmp/enrollment-check.log 2>&1; then
  echo "Unexpected access to enrollment secrets"; exit 1
fi
grep -q 'permission denied' /tmp/enrollment-check.log
echo "PASS: distinct password login, ingest role permitted, web/auth and secret reads denied"
