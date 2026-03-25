# Review Context Inventory

## Scope
This inventory covers the current `review` boundary inside `python-services/ai-proveedores`.

## Purpose
Classify the current files involved in review so we can split the context without breaking production.

## Classification Key

- **Keep**: belongs naturally to `review` and should move into the new bounded context.
- **Bridge**: can stay temporarily as a compatibility or routing bridge during migration.
- **Retire later**: likely removable after consumers are switched to the new context.

## File-by-file inventory

### `flows/constructores/construidor_verificacion.py`
- **Status**: Keep
- **Why**: This is the core constructor for review responses.
- **Target**: Move to `routes/review/` or `services/review/` depending on whether we keep response construction close to routing or policy.
- **Notes**: It currently mixes review response text with menu payload assembly, so it should be split if maintenance is separated.

### `templates/verificacion/estados.py`
- **Status**: Keep
- **Why**: This is the canonical copy for review and verification messages.
- **Target**: Stay under `templates/review/` in the new structure.
- **Notes**: This file should be the source of truth for review wording.

### `services/sesion_proveedor.py`
- **Status**: Bridge
- **Why**: It currently resolves state, synchronizes flow with the persisted profile, and contains review policy behavior.
- **Target**: Keep the session synchronization here for now, but delegate review entry to `routes/review/`.
- **Retire later**: The review-specific decisioning inside it should disappear once the review boundary is the only entry path.

### `routes/review/router.py`
- **Status**: Keep
- **Why**: This is now the review entry boundary and owns the handoff between pending verification, limited menu, and approval release.
- **Target**: Stay as the thin review router while `services/review/` owns the policy helpers.
- **Notes**: This should remain the single place that decides whether a review-state provider gets silenced, moved to the limited menu, or released to the main menu.

### `flows/router.py`
- **Status**: Bridge
- **Why**: It is the top-level orchestrator and currently decides whether a message should go to onboarding, review, or maintenance.
- **Target**: Keep as the main dispatcher, but delegate review to `routes/review/`.
- **Retire later**: The review branch should stay delegated and not regain local review policy.

### `flows/onboarding/handlers/redes_sociales.py`
- **Status**: Bridge
- **Why**: It still transitions the user into `pending_verification` after onboarding completion.
- **Target**: Keep the handoff for now, but remove review policy from this handler.
- **Retire later**: Once onboarding hands off to review explicitly, this file should only end onboarding and emit a transition event or state.

### `flows/gestores_estados/gestor_confirmacion_servicios.py`
- **Status**: Bridge
- **Why**: It still pushes the provider into `pending_verification` after enough services are captured.
- **Target**: Keep the transition for now while onboarding and review are separated.
- **Retire later**: When onboarding review handoff is extracted, this file should stop knowing anything about review policy.

### `flows/gestores_estados/gestor_confirmacion.py`
- **Status**: Bridge
- **Why**: It can still send the provider to review as part of the final confirmation path.
- **Target**: Keep only the handoff behavior during migration.
- **Retire later**: Remove any direct review response construction once the new review context is active.

### `constructores` and `templates` references to review inside menu flows
- **Status**: Bridge
- **Why**: Some menu constructors still reuse review response payloads.
- **Target**: Separate menu construction from review messaging.
- **Retire later**: Remove shared menu/review response coupling after maintenance is introduced.

## What should be removed last
These items should not be deleted until `review` is fully wired and production traffic is stable:

- review response constructors still referenced by onboarding
- menu/review coupling in shared constructors

## Recommended migration sequence
1. Extract review policy into `services/review/`.
2. Create `routes/review/router.py`.
3. Move review messages into `templates/review/`.
4. Reduce review code in `flows/router.py`.
5. Strip review knowledge from onboarding handlers.
6. Remove bridges once the new route owns the behavior.
