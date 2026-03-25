# Provider Context Audit

## Scope
Audit focused only on `python-services/ai-proveedores`.

## Goal
Identify wrappers, facades, legacy bridges, and true state values that should be kept, migrated, or retired.

## Summary
Most of the apparent "flags" in `ai-proveedores` are not feature flags. They are domain state:

- `pending_verification`
- `approved_basic`
- `profile_pending_review`
- `verification_notified`
- `review_silenced`
- `pending_review_attempts`

These should stay because they represent business state, not deployment toggles.

## Findings

### Keep for now: intentional compatibility facades
These modules are thin compatibility layers or centralized exports. They are not removal candidates until the new contexts are fully wired.

- [models/__init__.py](/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/models/__init__.py)
  - Central export point for models.
  - Still serves as a facade for domain imports.

- [infrastructure/database/__init__.py](/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/infrastructure/database/__init__.py)
  - Keeps `run_supabase` as a backward-compatible alias.

### Keep for now: legacy operational bridges
These are not pure wrappers, but they still support live runtime paths and should only be retired after the remaining compatibility window closes.

- [flows/maintenance/menu.py](/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/flows/maintenance/menu.py)
- [flows/maintenance/services.py](/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/flows/maintenance/services.py)
- [flows/maintenance/services_confirmation.py](/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/flows/maintenance/services_confirmation.py)
- [flows/maintenance/confirmation.py](/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/flows/maintenance/confirmation.py)
- [flows/maintenance/views.py](/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/flows/maintenance/views.py)
- [flows/maintenance/wait_experience.py](/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/flows/maintenance/wait_experience.py)
- [flows/maintenance/wait_social.py](/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/flows/maintenance/wait_social.py)

### Keep: state flags, not feature flags
These are business states and should not be removed as cleanup:

- `pending_verification`
- `approved_basic`
- `profile_pending_review`
- `verification_notified`
- `review_silenced`
- `pending_review_attempts`
- `onboarding_services_edit_action`
- `onboarding_services_edit_replace_select`
- `onboarding_services_edit_replace_input`
- `onboarding_services_edit_delete_select`
- `onboarding_services_edit_add`

### Keep: runtime configuration
These are configuration knobs, not feature flags:

- `os.getenv(...)` values for URLs, ports, timeouts, and models
- internal token checks
- Supabase/OpenAI/Redis wiring

## Removal candidates after migration
These are candidates for later removal once consumers have been updated:

- `infrastructure/database/__init__.py` alias `run_supabase`
- compatibility wording in `models/__init__.py`
- compatibility logic inside `flows/onboarding/router.py`

## Recommended cleanup order
1. Keep the runtime docs aligned to the current package layout.
2. Retire compatibility facades that no longer have consumers.
3. Remove onboarding/menu cross-dependencies where they still exist.
4. Update docs and tests to match the live boundaries.
