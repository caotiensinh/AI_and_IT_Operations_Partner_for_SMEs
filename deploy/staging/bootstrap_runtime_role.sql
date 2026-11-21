-- Applied only by database migrator, never by API.
-- psql variable :runtime_password must be supplied from environment.
SELECT format('CREATE ROLE sme_runtime LOGIN PASSWORD %L', :'runtime_password')
 WHERE NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='sme_runtime')
\gexec
SELECT format('ALTER ROLE sme_runtime PASSWORD %L', :'runtime_password')
\gexec
GRANT sme_app TO sme_runtime;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON DATABASE sme FROM PUBLIC;
GRANT CONNECT ON DATABASE sme TO sme_runtime;
