---
date: 2026-04-02T02:25:00Z
task_number: 1
task_total: 1
status: success
---

# Task Handoff: Migración de Identidad Visible a `first_name` / `last_name`

## Task Summary
Se migró la identidad visible de proveedor para que los flujos nuevos usen `first_name` / `last_name` como fuente canónica, dejando `full_name` solo como compatibilidad legada en persistencia o payloads antiguos.

## What Was Done
- Se centralizó la resolución de nombre visible en helpers compartidos para `ai-proveedores` y `ai-clientes`.
- Se removieron fallbacks de `full_name` en los puntos de render de onboarding, revisión, mantenimiento y menú.
- Se ajustaron los resolvers de `ai-clientes` para renderizar tarjetas, detalle y disponibilidad desde `first_name` / `last_name`.
- Se actualizó el BFF/frontend para construir mensajes y vistas de proveedor desde `first_name` / `last_name`.
- Se alinearon pruebas unitarias de Python y Node a la nueva fuente de identidad.
- Se limpió un import muerto y se ajustó tipado en `python-services/ai-proveedores/principal.py` para que el validador de calidad pase.

## Files Modified
- `python-services/ai-proveedores/services/shared/identidad_proveedor.py` - helpers canónicos de nombre visible.
- `python-services/ai-proveedores/services/onboarding/registration/normalizacion.py` - derivación de `full_name` desde `first_name` / `last_name`.
- `python-services/ai-proveedores/services/onboarding/registration/validacion_registro.py` - validación sin fallback a `full_name`.
- `python-services/ai-proveedores/services/onboarding/registration/determinador_estado.py` - fin del criterio de registro basado en `full_name`.
- `python-services/ai-proveedores/services/review/state.py` - resolución de nombre visible para revisión.
- `python-services/ai-proveedores/flows/router.py` - respuesta de revisión usando nombre canónico.
- `python-services/ai-proveedores/flows/maintenance/views.py` - vista personal usando `first_name` / `last_name`.
- `python-services/ai-proveedores/flows/maintenance/menu.py` y `flows/constructors/menu.py` - menú basado en nombre canónico.
- `python-services/ai-proveedores/services/onboarding/confirmacion.py` - mensaje de aprobación con nombre canónico.
- `python-services/ai-clientes/services/proveedores/identidad.py` - helper canónico de identidad visible.
- `python-services/ai-clientes/templates/proveedores/conexion.py` y `services/proveedores/conexion.py` - contacto/proveedor desde `first_name` / `last_name`.
- `python-services/ai-clientes/templates/proveedores/detalle.py` y `templates/proveedores/listado.py` - render visible canónico.
- `python-services/ai-clientes/services/proveedores/disponibilidad.py` y `flows/enrutador.py` - disponibilidad y candidato con nombre canónico.
- `python-services/ai-clientes/infrastructure/clientes/busqueda.py` - mapeo de búsqueda con `first_name` / `last_name`.
- `nodejs-services/frontend/bff/provider_messaging.js` y `bff/providers.js` - mensajes y resolutores de proveedor migrados.
- `nodejs-services/frontend/tests/bff/provider_messaging.test.js` y tests Python asociados - alineación de contratos.

## Decisions Made
- `first_name` es el nombre corto canónico de UI.
- `first_name + last_name` es el nombre visible compuesto.
- `full_name` queda solo como legado temporal en datos, no como fuente de negocio.
- No se tocó el contrato de clientes ni la persistencia de clientes.

## Patterns/Learnings for Next Tasks
- Conviene reutilizar helpers compartidos de identidad para evitar reintroducir fallbacks dispersos.
- El validador de calidad de Python puede arrastrar archivos no tocados por esta migración; conviene revisar el scope antes de asumir que un error es propio.
- En frontend Node, `eslint` y `prettier` pueden requerir una pasada explícita después de cambios de contrato.

## TDD Verification
- [x] Tests written BEFORE implementation
- [x] Each test failed first (RED), then passed (GREEN)
- [x] Tests run: `pytest -q python-services/ai-proveedores/tests/unit/test_review_router.py python-services/ai-proveedores/tests/unit/test_sesion_proveedor.py` -> 29 passed
- [x] Tests run: `pytest -q python-services/ai-clientes/tests/unit/test_conexion_contacto_ui.py python-services/ai-clientes/tests/unit/test_buscador_proveedores.py` -> 5 passed
- [x] Tests run: `node --test nodejs-services/frontend/tests/bff/provider_messaging.test.js` -> 4 passed
- [x] Refactoring kept tests green

## Code Quality (if qlty available)
- `python3 validate_quality.py --service ai-proveedores` -> passed all blocking checks
- `npx prettier --check bff/providers.js bff/provider_messaging.js tests/bff/provider_messaging.test.js` -> passed
- `npx eslint bff/providers.js bff/provider_messaging.js tests/bff/provider_messaging.test.js` -> passed with 1 non-blocking warning
- `npm run quality-check` at frontend root still reports unrelated pre-existing formatting warnings in other files

## Issues Encountered
- `validate_quality.py` initially failed because `python` was not available in PATH; `python3` worked.
- Full frontend quality-check is blocked by unrelated repository-wide Prettier warnings outside this migration.

## Next Task Context
- If we want to fully retire `full_name`, the next pass should be data-contract cleanup only, after confirming no external consumers still rely on it.
- The current change set is safe as a staged migration: UI uses `first_name` / `last_name`, legacy payloads still flow through `full_name` when required.
