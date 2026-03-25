# Provider Context Audit

## Scope
Audit focused only on `python-services/ai-proveedores`.

## Goal
Identify wrappers, facades, legacy bridges, and true feature toggles that should be kept, migrated, or retired as part of the provider-context split.

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
  - Contains compatibility wording, but it is mostly an import facade.

- [infrastructure/database/__init__.py](/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/infrastructure/database/__init__.py)
  - Keeps `run_supabase` as a backward-compatible alias.

### Keep for now: legacy operational bridges
These are not pure wrappers, but they still support live runtime paths and should only be retired after the maintenance split.

- [flows/gestores_estados/gestor_menu.py](/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/flows/gestores_estados/gestor_menu.py)
- [flows/gestores_estados/gestor_servicios.py](/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/flows/gestores_estados/gestor_servicios.py)
- [flows/gestores_estados/gestor_confirmacion_servicios.py](/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/flows/gestores_estados/gestor_confirmacion_servicios.py)
- [flows/gestores_estados/gestor_confirmacion.py](/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/flows/gestores_estados/gestor_confirmacion.py)
- [flows/gestores_estados/gestor_documentos.py](/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/flows/gestores_estados/gestor_documentos.py)
- [flows/gestores_estados/gestor_espera_experiencia.py](/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/flows/gestores_estados/gestor_espera_experiencia.py)
- [flows/gestores_estados/gestor_espera_red_social.py](/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores/flows/gestores_estados/gestor_espera_red_social.py)

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
These are candidates for later removal once `review` and `maintenance` are fully separated and consumers have been updated:

- `infrastructure/database/__init__.py` alias `run_supabase`
- compatibility wording in `models/__init__.py`
- compatibility logic inside `flows/onboarding/router.py`

## Recommended cleanup order
1. Split `review`.
2. Split `maintenance`.
3. Remove onboarding/menu cross-dependencies.
4. Retire compatibility facades that no longer have consumers.
5. Update docs and tests to match the new boundaries.
