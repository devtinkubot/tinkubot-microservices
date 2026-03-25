# Provider Ownership Matrix

Scope: `python-services/ai-proveedores`

## Why this exists
We are moving `ai-proveedores` from a shared-state router toward four independent flows:

- `onboarding`
- `review`
- `maintenance`
- `availability`

This matrix records who owns each state, who reads it, who writes it, and whether it is still a bridge.

## Current Folder Model

The repo is moving toward the target folder model. Some folders already exist, and others are the planned destination for the remaining split:

```text
python-services/ai-proveedores/
├── flows/
│   ├── onboarding/
│   ├── review/
│   └── ...
├── routes/
│   ├── onboarding/
│   ├── availability/
│   ├── review/
│   └── maintenance/
├── services/
│   ├── availability/  # availability request/response helpers and Redis processor
│   ├── onboarding/
│   ├── review/
│   ├── maintenance/
│   ├── registration/
│   ├── provider/
│   └── shared/
└── templates/
    ├── onboarding/
    ├── review/
    ├── registration/
    ├── session/
    └── interface/
```

## Ownership Rules

- `owner` is the context that should ultimately decide the state.
- `writer` is the code path that currently emits the state.
- `reader` is the code path that still consumes or normalizes the state.
- `bridge` means the state is still allowed as compatibility glue.

## Matrix

| State | Owner | Writer | Reader | Bridge |
|---|---|---|---|---|
| `onboarding_consent` | onboarding | onboarding router | onboarding router | no |
| `onboarding_city` | onboarding | onboarding router | onboarding router | no |
| `onboarding_dni_front_photo` | onboarding | onboarding router | onboarding router | no |
| `onboarding_face_photo` | onboarding | onboarding router | onboarding router | no |
| `onboarding_experience` | onboarding | onboarding router | onboarding router | no |
| `onboarding_specialty` | onboarding | onboarding router | onboarding router | no |
| `onboarding_add_another_service` | onboarding | onboarding flow | onboarding flow | no |
| `onboarding_services_confirmation` | onboarding | onboarding flow | onboarding flow | no |
| `onboarding_services_edit_action` | onboarding | onboarding flow | onboarding flow | no |
| `onboarding_services_edit_replace_select` | onboarding | onboarding flow | onboarding flow | no |
| `onboarding_services_edit_replace_input` | onboarding | onboarding flow | onboarding flow | no |
| `onboarding_services_edit_delete_select` | onboarding | onboarding flow | onboarding flow | no |
| `onboarding_services_edit_add` | onboarding | onboarding flow | onboarding flow | no |
| `onboarding_social_media` | onboarding | onboarding flow | onboarding flow | no |
| `onboarding_real_phone` | onboarding | onboarding flow | onboarding flow | no |
| `pending_verification` | review | onboarding handoff, admin sync | review router | no |
| `maintenance_menu_option` | maintenance | maintenance router | maintenance router | no |
| `maintenance_service_action` | maintenance | maintenance router | maintenance router | no |
| `maintenance_active_service_action` | maintenance | maintenance router | maintenance router | no |
| `maintenance_service_remove` | maintenance | maintenance router | maintenance router | no |
| `maintenance_specialty` | maintenance | maintenance handlers | maintenance handlers | no |
| `maintenance_profile_service_confirmation` | maintenance | maintenance handlers | maintenance handlers | no |
| `maintenance_add_another_service` | maintenance | maintenance handlers | maintenance handlers | no |
| `maintenance_services_confirmation` | maintenance | maintenance handlers | maintenance handlers | no |
| `maintenance_profile_completion_confirmation` | maintenance | maintenance handlers | maintenance handlers | no |
| `maintenance_profile_completion_edit_action` | maintenance | maintenance handlers | maintenance handlers | no |
| `maintenance_services_edit_action` | maintenance | maintenance handlers | maintenance handlers | no |
| `maintenance_services_edit_replace_select` | maintenance | maintenance handlers | maintenance handlers | no |
| `maintenance_services_edit_replace_input` | maintenance | maintenance handlers | maintenance handlers | no |
| `maintenance_services_edit_delete_select` | maintenance | maintenance handlers | maintenance handlers | no |
| `maintenance_services_edit_add` | maintenance | maintenance handlers | maintenance handlers | no |
| `maintenance_social_media` | maintenance | maintenance handlers | maintenance handlers | no |
| `maintenance_experience` | maintenance | maintenance handlers | maintenance handlers | no |
| `maintenance_certificate` | maintenance | maintenance handlers | maintenance handlers | no |
| `maintenance_social_facebook_username` | maintenance | maintenance handlers | maintenance handlers | no |
| `maintenance_social_instagram_username` | maintenance | maintenance handlers | maintenance handlers | no |
| `awaiting_availability_response` | availability | shared router / availability route | availability route | yes |
| `awaiting_menu_option` | shared orchestration | router / menu | router / menu | yes |
| `awaiting_deletion_confirmation` | maintenance | maintenance menu / deletion route | maintenance deletion route | yes |
| `awaiting_personal_info_action` | maintenance | maintenance info route | maintenance info route | yes |
| `awaiting_professional_info_action` | maintenance | maintenance info route | maintenance info route | yes |
| `awaiting_face_photo_update` | legacy maintenance bridge | legacy input paths | maintenance handlers | yes |
| `awaiting_dni_front_photo_update` | legacy maintenance bridge | legacy input paths | maintenance handlers | yes |
| `awaiting_dni_back_photo_update` | legacy maintenance bridge | legacy input paths | maintenance handlers | yes |
| `awaiting_experience` | shared onboarding/maintenance bridge | legacy input paths | onboarding + maintenance handlers | yes |
| `awaiting_social_media` | maintenance social bridge | legacy input paths | maintenance social handler | yes |
| `onboarding_social_facebook_username` | onboarding | onboarding social handler | onboarding social handler | no |
| `onboarding_social_instagram_username` | onboarding | onboarding social handler | onboarding social handler | no |
| `awaiting_certificate` | shared onboarding/maintenance bridge | legacy input paths | onboarding + maintenance handlers | yes |
| `awaiting_profile_service_confirmation` | shared onboarding/maintenance bridge | legacy input paths | onboarding + maintenance handlers | yes |
| `awaiting_add_another_service` | shared onboarding/maintenance bridge | legacy input paths | onboarding + maintenance handlers | yes |
| `awaiting_services_confirmation` | shared onboarding/maintenance bridge | legacy input paths | onboarding + maintenance handlers | yes |
| `maintenance_profile_completion_confirmation` | maintenance | maintenance services route | maintenance services route | no |
| `maintenance_profile_completion_edit_action` | maintenance | maintenance services route | maintenance services route | no |
| `awaiting_services_edit_action` | shared onboarding/maintenance bridge | legacy input paths | onboarding + maintenance handlers | yes |
| `awaiting_services_edit_replace_select` | shared onboarding/maintenance bridge | legacy input paths | onboarding + maintenance handlers | yes |
| `awaiting_services_edit_replace_input` | shared onboarding/maintenance bridge | legacy input paths | onboarding + maintenance handlers | yes |
| `awaiting_services_edit_delete_select` | shared onboarding/maintenance bridge | legacy input paths | onboarding + maintenance handlers | yes |
| `awaiting_services_edit_add` | shared onboarding/maintenance bridge | legacy input paths | onboarding + maintenance handlers | yes |
| `confirm` | shared orchestration | confirmation flow | router / confirmation flow | no |

## Practical Reading

If a state is owned by:

- `onboarding`, it should never open the maintenance menu or reclaim a provider that Supabase already considers registered.
- `review`, it should never continue normal business operations.
- `maintenance`, it should never decide onboarding capture rules.
- `availability`, it should only handle provider responses to client-originated availability requests.

If a state still appears as a bridge, it means we still need compatibility for:

- persisted sessions
- legacy router paths
- reentry from older flows

## Folder Guidance

The folder plan is already heading in the right direction:

- `flows/onboarding` should own onboarding decisions
- `routes/onboarding` should own onboarding entry, consent, and confirmation
- `routes/review` should own review entry and silence
- `routes/availability` should own the provider-facing availability wait state
- `routes/maintenance` should own post-approval navigation
- `routes/maintenance/deletion` should own record-deletion confirmation
- `routes/maintenance/info` should own personal and professional submenu actions
- `services/onboarding`, `services/review`, `services/maintenance` should hold the business helpers for each context
- `services/availability` should hold the availability request/response helpers and Redis processor
- `services/shared` should only contain true shared primitives

## Next Step

The next cleanup should focus on moving any remaining business decision from the shared router into the context that owns the state.
