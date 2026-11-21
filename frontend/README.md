# SME Workspace UI (first working vertical slice)

React + TypeScript responsive shell, desktop navigation and mobile bottom navigation.
It displays only data returned by authenticated backend endpoints:
`GET /v1/me/tenants` and `GET /v1/tenants/{id}/assets`.
No fake incident or integration statistics; disabled metrics use "—".

## Development
```sh
cd frontend
npm install
npm run build
```

Production deployment must serve this SPA and API on the same trusted HTTPS origin,
with secure OIDC session cookies. No customer credentials, secrets or datasets
belong in frontend bundles. The browser login callback deployment, CSP/headers,
live Identity Provider E2E, accessibility testing and refresh/retry UX remain open.
