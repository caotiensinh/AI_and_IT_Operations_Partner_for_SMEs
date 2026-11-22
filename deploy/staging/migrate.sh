#!/bin/sh
set -eu
: "${SME_DB_ADMIN_PASSWORD:?Missing database admin secret}"
: "${SME_RUNTIME_DB_PASSWORD:?Missing app secret}"
: "${SME_INGEST_DB_PASSWORD:?Missing ingest secret}"
: "${SME_DISPATCH_DB_PASSWORD:?Missing dispatch secret}"
: "${SME_STEPUP_DB_PASSWORD:?Missing step-up secret}"
: "${SME_APPROVAL_DB_PASSWORD:?Missing approval secret}"
export PGPASSWORD="$SME_DB_ADMIN_PASSWORD"
for file in /migrations/*.sql; do
  echo "Applying $(basename "$file")"
  psql -X -v ON_ERROR_STOP=1 -h db -U postgres -d sme -f "$file" >/dev/null
done
psql -X -v ON_ERROR_STOP=1 -h db -U postgres -d sme \
  -v runtime_password="$SME_RUNTIME_DB_PASSWORD" \
  -f /deploy/bootstrap_runtime_role.sql >/dev/null
psql -X -v ON_ERROR_STOP=1 -h db -U postgres -d sme \
  -v ingest_password="$SME_INGEST_DB_PASSWORD" \
  -f /deploy/bootstrap_ingest_role.sql >/dev/null
psql -X -v ON_ERROR_STOP=1 -h db -U postgres -d sme \
  -v dispatch_password="$SME_DISPATCH_DB_PASSWORD" \
  -f /deploy/bootstrap_dispatch_role.sql >/dev/null
psql -X -v ON_ERROR_STOP=1 -h db -U postgres -d sme \
  -v stepup_password="$SME_STEPUP_DB_PASSWORD" \
  -v approval_password="$SME_APPROVAL_DB_PASSWORD" \
  -f /deploy/bootstrap_stepup_roles.sql >/dev/null
echo "Staging web, ingest, dispatch, step-up issuer and approver logins initialized"
