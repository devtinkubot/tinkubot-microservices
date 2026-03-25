# Provider Context Split Plan

## Goal
Separate the provider journey into three explicit bounded contexts:

- `onboarding`: initial provider signup and data capture
- `review`: approval state, retry handling, and silence policy
- `maintenance`: post-approval menu and profile operations

## Why this exists
The current codebase mixes onboarding, review, and menu behavior in the same routing and service layers. That makes the provider journey harder to understand, test, and evolve safely.

## Scope
This migration is gradual. We will not rewrite the whole service.

### In scope
- Create new folders for `review` and `maintenance`
- Move review decision logic out of the shared router
- Move menu and post-approval operations out of onboarding paths
- Keep onboarding focused on the initial registration flow
- Keep `models`, `config`, and `infrastructure` in place

### Out of scope
- A full rewrite of the service
- Removing current persistence layers
- Renaming every module at once
- Changing the runtime container layout beyond what is needed for compatibility

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

## Migration order
1. Extract review policy and review responses.
2. Move the central review decision out of the shared router.
3. Introduce a maintenance context for the menu and profile operations.
4. Clean onboarding so it only covers the registration journey.
5. Reduce the role of `services/registration` to persistence and validation support.

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
