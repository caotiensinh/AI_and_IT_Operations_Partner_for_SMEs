# Docker build-context security

A staging workflow generates `.env.staging` with disposable credentials. Docker
uses the project root as build context, so merely omitting the file from `COPY`
does not prevent it from being sent to the build engine.

Root `.dockerignore` explicitly excludes environment files, private metadata,
local cache, container outputs, browser reports and database dumps. Both
`Dockerfile.api` and `Dockerfile.ui` must continue copying only necessary
source and configuration files.

**Verification:** staging Compose image build remains green in CI. Credential
scan of final image layers, signed SBOM, pinned image digests and secret-manager
injection remain release gates. Do not use a real customer secret in staging.
