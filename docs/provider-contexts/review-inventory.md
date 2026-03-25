# Review Context Inventory

## Scope
This inventory documents the current review boundary inside `python-services/ai-proveedores`.

## Purpose
Record the review-facing files that now exist so future cleanup does not reintroduce the old migration vocabulary.

## Classification Key

- **Own**: part of the live review boundary.
- **Bridge**: compatibility or orchestration glue that still serves live paths.
- **Historical**: an old file name or layout from before the split.

## Live review boundary

### `routes/review/router.py`
- **Status**: Own
- **Why**: This is the review entrypoint and decides the handoff between pending verification, limited menu, and approval release.

### `services/review/state.py`
- **Status**: Own
- **Why**: Holds review-state helpers and the rules for the current review boundary.

### `services/review/messages.py`
- **Status**: Own
- **Why**: Owns the review-facing copy and response messages.

### `templates/review/estados.py`
- **Status**: Own
- **Why**: Holds the review wording exposed to the user.

### `flows/router.py`
- **Status**: Bridge
- **Why**: It still orchestrates the top-level handoff across onboarding, review, maintenance, and availability.
- **Notes**: It should stay thin and avoid regaining review policy.

### `services/sesion_proveedor.py`
- **Status**: Bridge
- **Why**: It still synchronizes persisted state with the live session.
- **Notes**: Any review-specific decisioning should remain delegated to `routes/review/`.

## Historical names

These names appeared in the migration and are kept here only as history or documentation artifacts:

- `flows/constructores/construidor_verificacion.py`
- `templates/verificacion/estados.py`
- `flows/gestores_estados/gestor_confirmacion.py`
- `flows/gestores_estados/gestor_confirmacion_servicios.py`

## What not to do

- Do not reintroduce review policy inside `flows/router.py`.
- Do not move review copy back into the generic maintenance templates.
- Do not treat `pending_verification` as a generic maintenance state.

## Reading rule

If a change touches review, prefer the following order:

1. `routes/review/`
2. `services/review/`
3. `templates/review/`
4. `flows/router.py` only for orchestration
