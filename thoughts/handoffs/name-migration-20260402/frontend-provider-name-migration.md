# Frontend Handoff: Provider Name Migration

Date: 2026-04-02
Owner: Worker 3
Scope: `nodejs-services/frontend` only

## What Changed

- Updated provider-visible name resolution in `nodejs-services/frontend/bff/provider_messaging.js` to prefer `first_name` / `last_name` and only use legacy presentation fields as fallback.
- Updated `nodejs-services/frontend/bff/providers.js` so provider records exposed by the BFF resolve visible names from canonical first/last fields.
- Fixed the provider detail normalization path so the dashboard receives `documentFirstNames` / `documentLastNames` and canonical `name` / `displayName` values.
- Updated the monetization summary path to fetch and render `first_name` / `last_name` instead of relying on `display_name`, `document_*`, or `full_name`.
- Added/updated tests:
  - `nodejs-services/frontend/tests/bff/provider_messaging.test.js`
  - `nodejs-services/frontend/tests/bff/providers_name_resolution.test.js`

## Decisions

- `first_name` + `last_name` are now the canonical visible source for provider labels, contact cards, and approval/rejection messages.
- `full_name` is no longer the default source for visible names in the frontend BFF.
- Legacy compatibility is limited to older presentation fields (`display_name`, `formatted_name`) when canonical fields are missing.
- `fullName` remains in the normalized payload only as a derived compatibility field, not as the source of truth.

## Validation

- `node --test nodejs-services/frontend/tests/bff/provider_messaging.test.js nodejs-services/frontend/tests/bff/providers_reset.test.js nodejs-services/frontend/tests/bff/providers_name_resolution.test.js`
- `node --check nodejs-services/frontend/bff/provider_messaging.js nodejs-services/frontend/bff/providers.js`
- `npx prettier --check nodejs-services/frontend/bff/provider_messaging.js nodejs-services/frontend/bff/providers.js nodejs-services/frontend/tests/bff/provider_messaging.test.js nodejs-services/frontend/tests/bff/providers_reset.test.js nodejs-services/frontend/tests/bff/providers_name_resolution.test.js`

## Risks / Follow-up

- If any legacy provider rows still lack `first_name` / `last_name`, they will now fall back to `"Proveedor sin nombre"` or `"Proveedor"` instead of `full_name`.
- The dashboard module still contains its own fallback logic, but it now receives canonical fields from the BFF and should render the right visible name.
- I did not touch Python services or other workers' write sets.
