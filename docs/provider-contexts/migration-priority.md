# Provider Migration Priority

Scope: `python-services/ai-proveedores`

## Goal
Make `onboarding`, `review`, `maintenance`, and `availability` independent without a big-bang rewrite.

## Priority Order

### 1. Review boundary first

Why first:

- It is the cleanest business boundary.
- It already has its own entrypoint.
- It owns the approval gate and silence policy.

What to keep moving:

- `pending_verification` handling
- limited-menu behavior for pending providers
- approval/rejection response policy

What to avoid:

- menu logic that belongs to maintenance
- onboarding capture logic

### 2. Maintenance ownership second

Why second:

- It is the largest source of shared-router noise.
- It currently owns menu, edits, profile views, services, and social updates.

What to keep moving:

- menu entry and menu recovery
- profile and social editing
- service add/remove/replace
- profile completion and approval follow-up
- detail views that lead into maintenance edits

What to avoid:

- onboarding capture steps
- review-only policy

### 3. Onboarding simplification third

Why third:

- Onboarding is already the cleanest of the three, but it still shares some edit and state bridges.
- It should become the narrowest possible capture flow.

What to keep moving:

- capture steps
- onboarding-only service edit flow
- transition to review

What to avoid:

- menu entry
- post-approval edits

### 4. Availability as its own context

Why fourth:

- It is a distinct client-originated interaction with its own route and processor boundaries.
- The remaining work is documentation, tests, and any future naming cleanup, not boundary extraction.

What to keep moving:

- provider-facing wait state
- availability session reminder
- Redis-backed response processor

What to avoid:

- onboarding capture steps
- review approval/silence logic
- maintenance menu/edit logic

### 5. Shared orchestration cleanup last

Why last:

- The shared router still holds live orchestration states.
- Some `awaiting_*` names are business states, not dead aliases.

What to do:

- keep the router thin
- move logic behind context routers when a state has a clear owner
- leave business states alone until a context owns them fully

## Suggested Execution Sequence

1. Keep `review` as its own gate.
2. Keep moving menu/profile/social/service branches into `routes/maintenance`.
3. Continue extracting availability into `routes/availability` and `services/availability`.
4. Reduce `flows/router.py` to orchestration and legacy compatibility only.
5. Split onboarding bridges only where a state no longer serves both flows.
6. Retire aliases only after repo-wide search shows no live readers or writers.

## Shared Router Branch Priority

These are the current branches in `flows/router.py`, ordered by how likely they are to move next:

### High priority

- `awaiting_availability_response`

Why:

- availability now has dedicated route and processor boundaries, so it is no longer part of the shared-router cleanup

### Moved out

- `awaiting_deletion_confirmation`

Why:

- it is a maintenance menu action, not shared orchestration
- it now has its own maintenance deletion boundary
- the shared router no longer needs to know about the confirmation flow

### Medium priority

- `awaiting_personal_info_action`
- `awaiting_professional_info_action`

Why:

- they are router-level submenu coordinators
- they are maintenance-owned business states
- they are now good candidates for a thin subrouter module

### Keep for now

- `pending_verification`

Why:

- this is review-owned and already has its own policy path
- the remaining work here is not moving the state, but tightening the boundary around it

## Recommended Next Move

The next practical extraction is:

1. keep availability documentation and tests aligned with the canonical processor boundary
2. leave deletion confirmation in `routes/maintenance/deletion`
3. keep personal/professional submenu actions in `routes/maintenance/info`
4. keep onboarding normalization focused on the live onboarding aliases only

This gives us a safe, incremental path toward a thinner router without breaking the active business states.

## What This Means in Practice

- If a state is about approval, it belongs to `review`.
- If a state is about operating a registered provider, it belongs to `maintenance`.
- If a state is about collecting provider data, it belongs to `onboarding`.
- If a state is about responding to client-originated availability requests, it belongs to `availability`.
- If a state still serves more than one journey, it stays as a bridge until the journeys are split.

## Folder View

The folder layout is already aligned with this plan:

- `flows/onboarding`
- `routes/review`
- `routes/maintenance`
- `services/onboarding`
- `services/review`
- `services/maintenance`
- `services/shared`

The remaining work is mostly about moving ownership, not creating more folders.
