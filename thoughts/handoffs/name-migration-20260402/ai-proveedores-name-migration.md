---
date: 2026-04-02T02:28:10Z
owner: Worker 1
scope: python-services/ai-proveedores
status: success
---

# Handoff: Provider Visible Identity Migration in `ai-proveedores`

## Summary
Completed the provider identity migration inside `ai-proveedores` so visible labels now come from `first_name` / `last_name`, with `first_name` preferred for short labels. `full_name` remains only as legacy compatibility data and is no longer the source of truth for business decisions or rendered UI in this service.

## What Changed
- Added a single canonical helper at `python-services/ai-proveedores/services/shared/identidad_proveedor.py`.
- Removed duplicate helper files introduced during the migration.
- Updated onboarding normalization and validation to derive visible identity from `first_name` / `last_name`.
- Removed `full_name` from registration state decisions in `determinador_estado.py`.
- Updated review, maintenance, confirmation, menu, and view flows to render provider names from `first_name` / `last_name`.
- Fixed formatting in the `select(...)` blocks touched in:
  - `python-services/ai-proveedores/services/onboarding/registration/reinicio_onboarding_proveedor.py`
  - `python-services/ai-proveedores/services/onboarding/registration/limpieza_onboarding_proveedores.py`
- Added compatibility exports in `python-services/ai-proveedores/principal.py` for existing unit tests that monkeypatch Redis helpers.

## Files Touched
- `python-services/ai-proveedores/services/shared/identidad_proveedor.py`
- `python-services/ai-proveedores/models/proveedores.py`
- `python-services/ai-proveedores/services/onboarding/registration/normalizacion.py`
- `python-services/ai-proveedores/services/onboarding/registration/validacion_registro.py`
- `python-services/ai-proveedores/services/onboarding/registration/determinador_estado.py`
- `python-services/ai-proveedores/services/onboarding/registration/reinicio_onboarding_proveedor.py`
- `python-services/ai-proveedores/services/onboarding/registration/limpieza_onboarding_proveedores.py`
- `python-services/ai-proveedores/services/review/state.py`
- `python-services/ai-proveedores/routes/review/router.py`
- `python-services/ai-proveedores/flows/maintenance/views.py`
- `python-services/ai-proveedores/flows/maintenance/menu.py`
- `python-services/ai-proveedores/flows/constructors/menu.py`
- `python-services/ai-proveedores/flows/maintenance/services_confirmation.py`
- `python-services/ai-proveedores/services/onboarding/confirmacion.py`
- `python-services/ai-proveedores/tests/unit/test_registro_proveedor_taxonomia.py`
- `python-services/ai-proveedores/tests/unit/test_review_router.py`
- `python-services/ai-proveedores/tests/unit/test_sesion_proveedor.py`
- `python-services/ai-proveedores/tests/unit/test_confirmacion_interactive.py`
- `python-services/ai-proveedores/principal.py`

## Decisions
- `first_name` is the canonical short visible label.
- `first_name + last_name` is the canonical full visible label.
- `full_name` stays only for legacy compatibility/persistence, not for rendering or flow decisions.
- `display_name` / `formatted_name` are not used as fallback sources for visible provider identity in business logic.

## Validation
- `pytest -q python-services/ai-proveedores/tests/unit/test_registro_proveedor_taxonomia.py python-services/ai-proveedores/tests/unit/test_review_router.py python-services/ai-proveedores/tests/unit/test_sesion_proveedor.py python-services/ai-proveedores/tests/unit/test_confirmacion_interactive.py`
  - `45 passed`
- `python3 validate_quality.py --service ai-proveedores`
  - passed all blocking checks: syntax, black, isort, flake8, mypy, bandit

## Notes on Full Unit Suite
- `pytest -q python-services/ai-proveedores/tests/unit` still shows unrelated legacy failures in:
  - `tests/unit/test_dedupe_media.py`
  - `tests/unit/test_gestor_espera_ciudad.py`
  - `tests/unit/test_principal_disponibilidad.py`
- Those failures are not caused by this identity migration. They are compatibility/behavior issues in other areas of `ai-proveedores`.

## Risks / Follow-up
- If we want to fully retire `full_name`, that should be a separate cleanup after confirming no external consumers depend on it.
- Legacy tests still depend on compatibility exports in `principal.py`; removing them will require a separate test cleanup pass.
- I did not touch `ai-clientes` or the frontend in this worker scope.
