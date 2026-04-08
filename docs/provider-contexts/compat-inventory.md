# Provider Compatibility Inventory

Status: Transitional
Audience: Backend / Arquitectura
Last reviewed: 2026-04-08
Canonical owner: `ai-proveedores`

## Purpose

This document inventories the compatibility surface that still exists in
`python-services/ai-proveedores` so cleanup can happen safely.

It is not a dead-code report.

Its purpose is to separate:

- compatibility that is still actively consumed
- bridges that are still written or normalized by runtime
- candidates for future removal once consumers disappear

## Scope

Reviewed areas:

- `routes/maintenance/compat_*`
- legacy `flows/maintenance/*` bridge handlers
- `routes/onboarding/router.py` compatibility delegation
- legacy `awaiting_*` state vocabulary still read or written by runtime

## Compatibility Facades in `routes/maintenance`

These files are still part of the active route graph and should be treated as
legacy active, not dead code.

| Facade | Current direct consumers | Legacy implementation it fronts | Suggested status |
|---|---|---|---|
| `routes/maintenance/compat_menu.py` | `routes/maintenance/menu.py`, `routes/maintenance/info.py` | `flows/maintenance/menu.py` | Keep for now |
| `routes/maintenance/compat_views.py` | `routes/maintenance/views.py`, `routes/maintenance/handlers/views.py` | `flows/maintenance/views.py` | Keep for now |
| `routes/maintenance/compat_deletion.py` | `routes/maintenance/deletion.py` | `flows/maintenance/deletion.py` | Keep for now |
| `routes/maintenance/compat_profile.py` | `routes/maintenance/handlers/profile.py` | `flows/maintenance/document_update.py`, `selfie_update.py`, `wait_certificate.py`, `wait_experience.py`, `wait_name.py` | Keep for now |
| `routes/maintenance/compat_services.py` | `routes/maintenance/handlers/services.py`, `routes/maintenance/handlers/social.py`, `routes/maintenance/handlers/profile.py` | `flows/maintenance/services.py`, `services_confirmation.py`, `social_update.py`, `specialty.py`, `wait_social.py` | Keep for now |

## Observed Legacy Bridge Files

These files are still fronted by route-level compatibility layers or remain
part of normalization/transition paths.

| Legacy bridge file | Evidence of active use | Suggested status |
|---|---|---|
| `flows/maintenance/menu.py` | still reached through `compat_menu.py` | Keep for now |
| `flows/maintenance/views.py` | still reached through `compat_views.py` | Keep for now |
| `flows/maintenance/deletion.py` | still reached through `compat_deletion.py` | Keep for now |
| `flows/maintenance/document_update.py` | still reached through `compat_profile.py` | Keep for now |
| `flows/maintenance/selfie_update.py` | still reached through `compat_profile.py` | Keep for now |
| `flows/maintenance/wait_certificate.py` | still reached through `compat_profile.py` | Keep for now |
| `flows/maintenance/wait_experience.py` | still reached through `compat_profile.py` and still writes legacy state names | Keep for now |
| `flows/maintenance/wait_name.py` | still reached through `compat_profile.py` | Keep for now |
| `flows/maintenance/services.py` | still reached through `compat_services.py` | Keep for now |
| `flows/maintenance/services_confirmation.py` | still reached through `compat_services.py` | Keep for now |
| `flows/maintenance/social_update.py` | still reached through `compat_services.py` | Keep for now |
| `flows/maintenance/specialty.py` | still reached through `compat_services.py` | Keep for now |
| `flows/maintenance/wait_social.py` | still reached through `compat_services.py` and still recognizes onboarding-prefixed states | Keep for now |

## Onboarding Compatibility Delegation

`routes/onboarding/router.py` still delegates to `flows.onboarding.router` via
`compat_onboarding`.

Observed delegation includes:

- city wait
- DNI front
- face photo
- real phone
- experience
- services
- consent
- social media
- add-another-service decision

Interpretation:

- The route boundary exists, but the runtime implementation is still bridged to
  the old flow layer.
- This is compatibility by design, not dead code.

Suggested status:

- Keep for now

## Legacy State Vocabulary Still Active

The presence of `awaiting_*` states in this codebase does not automatically
mean dead compatibility. Many are still written, normalized, or reconstructed
 from live runtime paths.

### Still clearly active in runtime or persistence paths

- `awaiting_menu_option`
- `awaiting_personal_info_action`
- `awaiting_professional_info_action`
- `awaiting_deletion_confirmation`
- `awaiting_face_photo_update`
- `awaiting_dni_front_photo_update`
- `awaiting_dni_back_photo_update`
- `awaiting_experience`
- `awaiting_social_media`
- `awaiting_certificate`
- `awaiting_add_another_service`
- `awaiting_services_confirmation`
- `awaiting_services_edit_action`
- `awaiting_services_edit_replace_select`
- `awaiting_services_edit_replace_input`
- `awaiting_services_edit_delete_select`
- `awaiting_services_edit_add`

Evidence sources:

- `flows/maintenance/context.py`
- `flows/router.py`
- `routes/maintenance/router.py`
- `routes/maintenance/handlers/profile.py`
- `routes/maintenance/handlers/services.py`
- `routes/maintenance/handlers/social.py`
- `services/availability/estados.py`
- `services/shared/estados_proveedor.py`
- `services/shared/orquestacion_whatsapp.py`
- `services/onboarding/progress.py`
- `services/review/menu.py`
- `tools/backfill/19_normalizar_estados_proveedores.sql`
- `tools/backfill/20_auditar_estados_proveedores.sql`
- `tests/unit/*`

Suggested status:

- Keep for now

### Meaning

These states should be treated as one of:

- still-live runtime vocabulary
- compatibility normalization vocabulary
- persistence/backfill vocabulary that still affects real data

They are not safe removal candidates until:

1. runtime stops writing them
2. runtime stops reading or normalizing them
3. tests stop asserting them
4. persisted rows and backfill tooling no longer depend on them

## Near-Term Cleanup Candidates

These are not safe to remove today, but they are reasonable candidates for the
next targeted cleanup pass once consumers are reduced.

### Group A: Route-level compatibility facades

Retirement gate:

- no route or handler imports them directly
- the route boundary calls new handlers/services directly
- tests no longer patch or assert legacy flow functions behind the facades

Candidates:

- `routes/maintenance/compat_menu.py`
- `routes/maintenance/compat_views.py`
- `routes/maintenance/compat_deletion.py`
- `routes/maintenance/compat_profile.py`
- `routes/maintenance/compat_services.py`

### Group B: Flow-level maintenance bridges

Retirement gate:

- no `compat_*` facade forwards into them
- replacement handlers own the state transitions directly
- no persisted legacy states re-enter them through the router

Candidates:

- `flows/maintenance/document_update.py`
- `flows/maintenance/wait_experience.py`
- `flows/maintenance/wait_name.py`
- `flows/maintenance/wait_social.py`
- `flows/maintenance/services_confirmation.py`
- `flows/maintenance/specialty.py`

### Group C: Legacy `awaiting_*` maintenance bridges

Retirement gate:

- no writers remain in route/flow/service code
- no readers remain in `availability`, `shared`, `review`, or onboarding
- no backfill scripts depend on them
- no tests assert them as current behavior

## Recommended Cleanup Order

1. Reduce imports into `routes/maintenance/compat_*` by moving consumers to
   direct route-owned handlers.
2. Remove one facade at a time only after its downstream bridge file becomes
   unused.
3. Retire flow-level maintenance bridges after route-level facades are gone.
4. Retire `awaiting_*` aliases only after runtime, tests, and backfills no
   longer reference them.

## Practical Rule

Do not remove compatibility files because they:

- contain `compat` in the filename
- use `awaiting_*`
- look older than neighboring files

Remove them only when:

- import graph says no live consumers remain
- state graph says no live reader/writer remains
- tests no longer treat them as expected behavior

## Current Verdict

Today, the compatibility surface in `ai-proveedores` is still:

- visible
- bounded
- partially documented
- actively consumed

That means it is a cleanup target, but not dead code yet.
