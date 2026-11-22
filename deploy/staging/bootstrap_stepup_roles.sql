-- Disposable staging ONLY. psql variables supplied by the migration container.
-- Password values are escaped using psql SQL-literal substitution; never logged.
SELECT format('CREATE ROLE sme_stepup_runtime LOGIN INHERIT PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', :'stepup_password')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sme_stepup_runtime')
\gexec
SELECT format('ALTER ROLE sme_stepup_runtime LOGIN INHERIT PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', :'stepup_password')
\gexec
SELECT format('CREATE ROLE sme_approval_runtime LOGIN INHERIT PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', :'approval_password')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sme_approval_runtime')
\gexec
SELECT format('ALTER ROLE sme_approval_runtime LOGIN INHERIT PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', :'approval_password')
\gexec
GRANT CONNECT ON DATABASE sme TO sme_stepup_runtime,sme_approval_runtime;
GRANT sme_stepup TO sme_stepup_runtime;
GRANT sme_approval TO sme_approval_runtime;
REVOKE sme_app,sme_auth,sme_ingest,sme_dispatch,sme_approval FROM sme_stepup_runtime;
REVOKE sme_app,sme_auth,sme_ingest,sme_dispatch,sme_stepup FROM sme_approval_runtime;
-- Do not grant either service principal to sme_runtime or staging API.
