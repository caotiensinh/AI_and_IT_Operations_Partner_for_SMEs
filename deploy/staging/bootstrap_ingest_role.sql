-- Operator-only staging role bootstrap; psql variable :ingest_password required.
-- Never grant sme_app or grant direct access to enrollment/sample tables.
SELECT format('CREATE ROLE sme_ingest_runtime LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', :'ingest_password')
 WHERE NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='sme_ingest_runtime')
\gexec
SELECT format('ALTER ROLE sme_ingest_runtime PASSWORD %L', :'ingest_password')
\gexec
GRANT sme_ingest TO sme_ingest_runtime;
GRANT CONNECT ON DATABASE sme TO sme_ingest_runtime;
REVOKE sme_app FROM sme_ingest_runtime;
REVOKE sme_auth FROM sme_ingest_runtime;
