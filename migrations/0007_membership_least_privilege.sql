-- Least privilege corrective migration for preexisting deployments.
-- Future clean installs already get read-only membership grant from 0001.
BEGIN;
REVOKE INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER
  ON sme.memberships FROM sme_app;
GRANT SELECT ON sme.memberships TO sme_app;
COMMIT;
