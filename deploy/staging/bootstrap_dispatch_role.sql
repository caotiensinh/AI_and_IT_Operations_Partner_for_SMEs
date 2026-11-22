SELECT format('CREATE ROLE sme_dispatch_runtime LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', :'dispatch_password')
 WHERE NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='sme_dispatch_runtime')
\gexec
SELECT format('ALTER ROLE sme_dispatch_runtime PASSWORD %L', :'dispatch_password')
\gexec
GRANT sme_dispatch TO sme_dispatch_runtime;
GRANT CONNECT ON DATABASE sme TO sme_dispatch_runtime;
REVOKE sme_app FROM sme_dispatch_runtime;
REVOKE sme_auth FROM sme_dispatch_runtime;
REVOKE sme_ingest FROM sme_dispatch_runtime;
