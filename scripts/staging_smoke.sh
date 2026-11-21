#!/bin/sh
set -eu
: "${SME_STAGING_ORIGIN:=http://127.0.0.1:18080}"
curl -fsS "$SME_STAGING_ORIGIN/" >/dev/null
status=$(curl -sS -o /dev/null -w '%{http_code}' "$SME_STAGING_ORIGIN/v1/me/tenants")
test "$status" = "401" || { echo "Expected anonymous 401, got $status"; exit 1; }
status=$(curl -sS -o /dev/null -w '%{http_code}' "$SME_STAGING_ORIGIN/v1/tenants/00000000-0000-0000-0000-000000000001/assets")
test "$status" = "401" || { echo "Expected anonymous assets 401, got $status"; exit 1; }
echo "PASS: staging UI serves, anonymous tenant/asset routes deny access"
