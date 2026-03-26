# Provider Context Split Plan

## Goal
Finish the provider journey split into explicit bounded contexts while keeping the current runtime layout stable:

- `onboarding`: initial provider signup and data capture
- `review`: approval state, retry handling, and silence policy
- `maintenance`: post-approval menu and profile operations
- `availability`: provider-facing response to availability requests

## Why this exists
The current codebase mixes onboarding, review, and menu behavior in the same routing and service layers. That makes the provider journey harder to understand, test, and evolve safely.

## Scope
This migration is gradual. The codebase is already partially split, so the remaining work is mostly boundary cleanup and documentation alignment.

### In scope
- Keep review decision logic out of the shared router
- Keep menu and post-approval operations out of onboarding paths
- Keep onboarding focused on the initial registration flow
- Keep `availability` independent from onboarding and maintenance
- Keep `models`, `config`, and `infrastructure` in place

### Out of scope
- A full rewrite of the service
- Removing current persistence layers
- Renaming every module at once
- Changing the runtime container layout beyond what is needed for compatibility

## Runtime Stack Size

This document describes the provider-boundary split, not an implemented worker topology.

The repo currently does **not** ship BullMQ workers. The live runtime remains:

- `wa-gateway`
- `frontend`
- `redis`
- `ai-clientes`
- `ai-proveedores`
- `ai-search`

If async workers are introduced later, their container shape should be documented alongside the implementation instead of being assumed here.

## Proposed boundaries

### Onboarding
Handles:
- consent
- city
- DNI
- selfie
- experience
- initial services
- submission to review

Ends when the provider enters review.

### Review
Handles:
- pending review state
- repeat message policy
- silence after repeated insistence
- approval transition

This is the boundary between registration and operations.

### Maintenance
Handles:
- menu
- view profile
- edit services
- edit social links
- edit documents
- certificates
- deletion or administrative maintenance

Starts only after approval.

### Availability
Handles:
- provider wait state for incoming availability requests
- Redis-backed response processing
- resume to menu or exit

## Migration order
1. Extract review policy and review responses.
2. Move the central review decision out of the shared router.
3. Introduce a maintenance context for the menu and profile operations.
4. Keep availability isolated behind its own route and processor.
5. Clean onboarding so it only covers the registration journey.
6. Reduce the role of shared bridges to the minimum required for compatibility.

## Success criteria
- Onboarding no longer leaks menu behavior
- Review is the only place that decides:
  - respond
  - silence
  - release to maintenance
- Maintenance is only available after approval
- The code structure matches the provider journey more clearly

## Compatibility rule
During migration, old modules can remain as facades or delegators if needed. We prefer gradual extraction over breaking imports.

## Documentation rule
The `runtime` split is documented as a conceptual boundary, not as a required physical folder move. The repo should keep reflecting the actual package layout that production imports use.
