#!/bin/sh
# Disposable CI/staging login proof. Never echo passwords, DSNs or query results.
set -eu
: "${SME_STEPUP_DB_PASSWORD:?missing issuer secret}"
: "${SME_APPROVAL_DB_PASSWORD:?missing approval secret}"
issuer_sql="SELECT session_user='sme_stepup_runtime' AND current_user='sme_stepup_runtime'
 AND has_function_privilege(current_user,'sme.issue_asahi_stepup(bytea,uuid,text,text,text,text,integer)','EXECUTE')
 AND has_function_privilege(current_user,'sme.begin_asahi_stepup_challenge(bytea,bytea,bytea,uuid,text,text,text,text,text,text)','EXECUTE')
 AND has_function_privilege(current_user,'sme.resolve_asahi_stepup_identity(bytea,uuid)','EXECUTE')
 AND has_function_privilege(current_user,'sme.lookup_asahi_stepup_challenge(bytea,bytea,bytea)','EXECUTE')
 AND NOT has_function_privilege(current_user,'sme.approve_asahi_delivery_stepup(bytea,uuid,uuid,text,text,text)','EXECUTE')
 AND NOT has_function_privilege(current_user,'sme.revoke_asahi_delivery_stepup(bytea,uuid,uuid)','EXECUTE')
 AND NOT has_table_privilege(current_user,'sme.sessions','SELECT')
 AND NOT has_table_privilege(current_user,'sme.asahi_stepup_proofs','INSERT')
 AND NOT has_table_privilege(current_user,'sme.asahi_delivery_destinations','UPDATE')
 AND NOT (SELECT rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb
  FROM pg_roles WHERE rolname=session_user)"
approval_sql="SELECT session_user='sme_approval_runtime' AND current_user='sme_approval_runtime'
 AND has_function_privilege(current_user,'sme.approve_asahi_delivery_stepup(bytea,uuid,uuid,text,text,text)','EXECUTE')
 AND has_function_privilege(current_user,'sme.revoke_asahi_delivery_stepup(bytea,uuid,uuid)','EXECUTE')
 AND NOT has_function_privilege(current_user,'sme.issue_asahi_stepup(bytea,uuid,text,text,text,text,integer)','EXECUTE')
 AND NOT has_function_privilege(current_user,'sme.begin_asahi_stepup_challenge(bytea,bytea,bytea,uuid,text,text,text,text,text,text)','EXECUTE')
 AND NOT has_function_privilege(current_user,'sme.resolve_asahi_stepup_identity(bytea,uuid)','EXECUTE')
 AND NOT has_function_privilege(current_user,'sme.lookup_asahi_stepup_challenge(bytea,bytea,bytea)','EXECUTE')
 AND NOT has_table_privilege(current_user,'sme.sessions','SELECT')
 AND NOT has_table_privilege(current_user,'sme.asahi_stepup_proofs','INSERT')
 AND NOT has_table_privilege(current_user,'sme.asahi_delivery_destinations','UPDATE')
 AND NOT (SELECT rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb
  FROM pg_roles WHERE rolname=session_user)"
export PGPASSWORD="$SME_STEPUP_DB_PASSWORD"
test "$(psql -X -At -v ON_ERROR_STOP=1 -h db -U sme_stepup_runtime -d sme -c "$issuer_sql")" = t
# Authorization checks must use the authenticated login, never SET ROLE as postgres.
if psql -X -v ON_ERROR_STOP=1 -h db -U sme_stepup_runtime -d sme -c 'SET ROLE sme_approval' >/dev/null 2>&1; then
  echo "FAIL: issuer can escalate into approval"; exit 1
fi
if psql -X -v ON_ERROR_STOP=1 -h db -U sme_stepup_runtime -d sme -c 'SELECT * FROM sme.asahi_stepup_challenges' >/dev/null 2>&1; then
  echo "FAIL: issuer can read raw step-up challenges"; exit 1
fi
export PGPASSWORD="$SME_APPROVAL_DB_PASSWORD"
test "$(psql -X -At -v ON_ERROR_STOP=1 -h db -U sme_approval_runtime -d sme -c "$approval_sql")" = t
if psql -X -v ON_ERROR_STOP=1 -h db -U sme_approval_runtime -d sme -c 'SET ROLE sme_stepup' >/dev/null 2>&1; then
  echo "FAIL: approver can escalate into step-up issuer"; exit 1
fi
if psql -X -v ON_ERROR_STOP=1 -h db -U sme_approval_runtime -d sme -c 'SELECT * FROM sme.asahi_stepup_proofs' >/dev/null 2>&1; then
  echo "FAIL: approver can read raw proofs"; exit 1
fi
echo "PASS: password-authenticated, distinct issuer and approver logins; denied cross-role escalation and raw table access"
