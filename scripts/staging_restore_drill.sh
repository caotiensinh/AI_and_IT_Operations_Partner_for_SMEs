#!/bin/sh
# Disposable CI-only backup + restore proof; never run against customer data.
set -eu
: "${SME_E2E_FIXTURE_MODE:?Require disposable_ci_only marker}"
[ "$SME_E2E_FIXTURE_MODE" = disposable_ci_only ] || { echo "Refusing non-disposable restore drill"; exit 1; }
compose="docker compose --env-file .env.staging -f compose.staging.yml"
# A test tenant exercises relational data, not only schema restore.
$compose exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d sme -c \
  "INSERT INTO sme.tenants(id,slug,display_name)
    VALUES ('00000000-0000-0000-0000-000000000099','restore-proof','Restore Proof')" >/dev/null
# pg_dump writes to runner workspace only; transient GitHub runner is destroyed.
$compose exec -T db pg_dump -U postgres -d sme --format=custom --no-owner --no-acl > /tmp/sme-staging-proof.dump
$compose exec -T db createdb -U postgres sme_restore
$compose exec -T db pg_restore -U postgres -d sme_restore --no-owner --no-acl < /tmp/sme-staging-proof.dump
actual=$($compose exec -T db psql -At -U postgres -d sme_restore -c \
  "SELECT count(*) FROM sme.tenants WHERE slug='restore-proof'")
[ "$actual" = 1 ] || { echo "Restore lost tenant proof row: $actual"; exit 1; }
# Verify row-level security configuration survives schema restore.
actual=$($compose exec -T db psql -At -U postgres -d sme_restore -c \
  "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname='sme' AND c.relname IN ('memberships','sites','assets')
   AND c.relrowsecurity AND c.relforcerowsecurity")
[ "$actual" = 3 ] || { echo "RLS policies missing after restore: $actual"; exit 1; }
echo "PASS: seeded tenant row and FORCE RLS restored in separate database."
