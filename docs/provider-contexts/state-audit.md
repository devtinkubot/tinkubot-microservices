# Provider State Audit

## Scope
Audit focused on `python-services/ai-proveedores`.

## Goal
Separate current runtime states into:

- onboarding
- maintenance
- review
- availability
- legacy awaiting aliases kept only for compatibility
- current runtime state names that must stay

## Summary
The service no longer needs the old service aliases:

- `awaiting_service_add`
- `awaiting_service_action`
- `awaiting_service_add_confirmation`

Those aliases were retired from runtime compatibility maps.

What remains under `awaiting_*` is mostly real state vocabulary or transition glue for active flows.

## Onboarding States
These belong to the initial provider journey and should stay in the onboarding context:

- `onboarding_consent`
- `onboarding_city`
- `onboarding_dni_front_photo`
- `onboarding_face_photo`
- `onboarding_experience`
- `onboarding_specialty`
- `onboarding_add_another_service`
- `onboarding_services_confirmation`
- `onboarding_services_edit_action`
- `onboarding_services_edit_replace_select`
- `onboarding_services_edit_replace_input`
- `onboarding_services_edit_delete_select`
- `onboarding_services_edit_add`
- `onboarding_social_media`
- `onboarding_real_phone`

Legacy onboarding aliases still exist only where they are used to normalize old state values:

- `awaiting_city`
- `awaiting_dni_front_photo`
- `awaiting_experience`
- `awaiting_specialty`
- `awaiting_add_another_service`
- `awaiting_services_confirmation`
- `awaiting_services_edit_action`
- `awaiting_services_edit_replace_select`
- `awaiting_services_edit_replace_input`
- `awaiting_services_edit_delete_select`
- `awaiting_services_edit_add`
- `awaiting_social_media_onboarding`
- `awaiting_consent`
- `awaiting_real_phone`

Route ownership:

- `routes/onboarding` owns onboarding entry, consent, and final confirmation
- `flows/onboarding/router.py` owns the state-specific onboarding transitions

## Maintenance States
These belong to the post-approval maintenance journey:

- `maintenance_menu_option`
- `maintenance_service_action`
- `maintenance_active_service_action`
- `maintenance_service_remove`
- `maintenance_specialty`
- `maintenance_profile_service_confirmation`
- `maintenance_add_another_service`
- `maintenance_services_confirmation`
- `maintenance_profile_completion_confirmation`
- `maintenance_profile_completion_edit_action`
- `maintenance_services_edit_action`
- `maintenance_services_edit_replace_select`
- `maintenance_services_edit_replace_input`
- `maintenance_services_edit_delete_select`
- `maintenance_services_edit_add`
- `maintenance_social_media`
- `maintenance_experience`
- `maintenance_certificate`
- `maintenance_social_facebook_username`
- `maintenance_social_instagram_username`

Maintenance also owns the profile submenu coordinators that used to sit in the shared router:

- `awaiting_personal_info_action`
- `awaiting_professional_info_action`

Legacy maintenance aliases are still present only where they normalize persisted state:

- `awaiting_menu_option`
- `awaiting_deletion_confirmation`
- `awaiting_active_service_action`
- `awaiting_service_remove`
- `awaiting_face_photo_update`
- `awaiting_dni_front_photo_update`
- `awaiting_dni_back_photo_update`
- `awaiting_experience`
- `awaiting_social_media` (maintenance social bridge)
- `onboarding_social_facebook_username`
- `onboarding_social_instagram_username`
- `awaiting_certificate`
- `awaiting_profile_service_confirmation`
- `awaiting_add_another_service`
- `awaiting_services_confirmation`
- `maintenance_profile_completion_confirmation`
- `maintenance_profile_completion_edit_action`
- `awaiting_services_edit_action`
- `awaiting_services_edit_replace_select`
- `awaiting_services_edit_replace_input`
- `awaiting_services_edit_delete_select`
- `awaiting_services_edit_add`

## Review States
The review boundary is intentionally narrow:

- `pending_verification`

Observed responsibilities:

- initial review entry
- limited-menu handoff when the provider is still pending
- silence and approval transitions

Interpretation:

- `routes/review` now owns the review entry decision
- `services/review` owns the review policy and response helpers

## Availability States
Availability is a separate provider-facing interaction that comes from client requests.

Observed responsibilities:

- remember the provider is waiting for an answer
- show the reminder copy when the provider replies
- route `menu`/`volver`/`salir` back to the main menu
- keep the Redis-backed request processor separate from the chat-state router

Interpretation:

- `awaiting_availability_response` is still the live session state today
- the availability route now owns the provider-facing wait state
- the Redis-backed response processor now lives in `services/availability/processor.py`
- the legacy availability shim has been retired

## Current Runtime States That Must Stay
These are not wrappers. They are active business states or orchestration states:

- `awaiting_menu_option`
- `pending_verification`
- `awaiting_availability_response`
- `confirm`
- `awaiting_deletion_confirmation`
- `awaiting_personal_info_action`
- `awaiting_professional_info_action`
- `maintenance_profile_completion_finalize`

## Removed Runtime Aliases
These were retired from compatibility maps:

- `awaiting_service_add`
- `awaiting_service_action`
- `awaiting_service_add_confirmation`

## Notes
- `awaiting_*` is not automatically legacy.
- Some `awaiting_*` names are still the live business vocabulary of the current system.
- The right test for removal is not the prefix, but whether the state is still written, read, or reconstructed from persisted runtime paths.
- `routes/availability` now owns the provider-facing wait state, while `services/availability/processor.py` holds the Redis-backed processor.

## Block Audit

### Onboarding
Current onboarding is still an active runtime boundary, not a dead wrapper layer.

Observed responsibilities:

- consent bootstrap
- city, document, selfie and phone capture
- experience and specialty capture
- onboarding-only service editing
- transition to `pending_verification`

Interpretation:

- the `onboarding_*` namespace is now the preferred vocabulary
- legacy `awaiting_*` onboarding aliases remain only as normalization bridges
- these aliases should stay until the onboarding router and persisted sessions are fully migrated

### Maintenance
Maintenance is already the home of post-approval editing and menu handling.

Observed responsibilities:

- menu entry
- profile views
- social updates
- service add/remove/replace flows
- deletion confirmation for the provider record
- profile completion flows

Interpretation:

- `maintenance_*` is the current target vocabulary
- legacy `awaiting_*` maintenance aliases are still present as compatibility bridges in the shared router and the profile-view router
- these aliases are not wrappers in the dead-code sense; they still normalize live state values and transitions

### Review
Review is the narrow boundary between onboarding and maintenance.

Observed responsibilities:

- normalize administrative status
- detect pending verification
- apply review response policy
- keep the provider quiet when required

Interpretation:

- `pending_verification` is a real business state, not a legacy alias
- review should continue to own silence and approval transitions

## Recommended Next Cleanup
The next safe refactor is not to delete more `awaiting_*` at random.

Preferred order:

1. shrink the shared router further
2. move more maintenance branches behind `routes/maintenance`
3. keep onboarding-only aliases until the persisted state window expires
4. retire any alias only after a repo-wide search shows no live reader or writer remains

## Documentation note

This audit is now a historical compatibility map, not a migration plan. The live code already uses `config`, `models`, `flows`, `routes`, `services`, `templates`, `infrastructure`, `utils`, `tools`, and `tests` as the actual package layout.
