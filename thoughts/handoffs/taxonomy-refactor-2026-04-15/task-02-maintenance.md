---
date: 2026-04-15T06:46:23+00:00
task_number: 2
task_total: 2
status: success
---

# Task Handoff: Maintenance Taxonomy Cleanup

## Task Summary
Canonicalizar los estados runtime de `maintenance` para dejar `maintenance_*` donde el contrato pertenece a mantenimiento, eliminar aliases legacy internos ya no necesarios y alinear los módulos `wait_*` con nombres de dominio coherentes.

## What Was Done
- Renombré los módulos `wait_*` de maintenance a `certificate_step.py`, `experience_step.py`, `name_step.py` y `social_step.py`.
- Actualicé imports de maintenance para usar los nuevos módulos renombrados.
- Cambié los estados de submenú y borrado a `maintenance_personal_info_action`, `maintenance_professional_info_action` y `maintenance_deletion_confirmation`.
- Reemplacé transiciones de mantenimiento que todavía emitían `awaiting_social_media` y `awaiting_certificate` por `maintenance_social_media` y `maintenance_certificate`.
- Cambié los arranques de documentos de maintenance para usar `maintenance_city` y `maintenance_dni_front_photo_update`.
- Eliminé aliases legacy internos en handlers de maintenance para estados `awaiting_*` que ya no emite este boundary.
- Ajusté pruebas de maintenance para afirmar la taxonomía canónica nueva y agregué cobertura para experiencia y arranque de documentos.
- Corregí un bug existente en `experience_step.py`: el payload de redes sociales se llamaba sin los kwargs requeridos.

## Files Modified
- `python-services/ai-proveedores/flows/maintenance/__init__.py` - imports actualizados a los módulos renombrados.
- `python-services/ai-proveedores/flows/maintenance/context.py` - conjunto de estados de mantenimiento actualizado a `maintenance_*`.
- `python-services/ai-proveedores/flows/maintenance/deletion.py` - docstring alineado con el estado canónico.
- `python-services/ai-proveedores/flows/maintenance/document_update.py` - inicio de flujos de documentos ahora usa `maintenance_city` y `maintenance_dni_front_photo_update`.
- `python-services/ai-proveedores/flows/maintenance/menu.py` - menú y submenús ahora emiten estados `maintenance_*`.
- `python-services/ai-proveedores/flows/maintenance/views.py` - padres de vistas personales/profesionales alineados con `maintenance_*`.
- `python-services/ai-proveedores/flows/maintenance/selfie_update.py` - docstring alineado con `maintenance_face_photo_update`.
- `python-services/ai-proveedores/flows/maintenance/certificate_step.py` - nuevo nombre de módulo para el paso de certificado.
- `python-services/ai-proveedores/flows/maintenance/experience_step.py` - nuevo nombre de módulo; transición a `maintenance_social_media`; fix del payload de redes.
- `python-services/ai-proveedores/flows/maintenance/name_step.py` - nuevo nombre de módulo para el paso de nombre.
- `python-services/ai-proveedores/flows/maintenance/social_step.py` - nuevo nombre de módulo; transición a `maintenance_social_media` y `maintenance_certificate`.
- `python-services/ai-proveedores/routes/maintenance/router.py` - router ajustado a los nuevos estados canónicos de maintenance.
- `python-services/ai-proveedores/routes/maintenance/handlers/profile.py` - imports renombrados y eliminación de aliases legacy internos.
- `python-services/ai-proveedores/routes/maintenance/handlers/social.py` - import renombrado y eliminación de alias legacy.
- `python-services/ai-proveedores/services/shared/estados_proveedor.py` - `MENU_POST_REGISTRO_STATES` ahora registra los estados de maintenance canónicos.
- `python-services/ai-proveedores/tests/unit/test_router_maintenance_menu.py` - expectativas actualizadas a `maintenance_*`.
- `python-services/ai-proveedores/tests/unit/test_router_maintenance_info.py` - expectativas actualizadas a `maintenance_*`.
- `python-services/ai-proveedores/tests/unit/test_router_maintenance_deletion.py` - expectativa actualizada a `maintenance_deletion_confirmation`.
- `python-services/ai-proveedores/tests/unit/test_router_maintenance_social.py` - cobertura para import nuevo y transición experiencia -> social canónica.
- `python-services/ai-proveedores/tests/unit/test_document_update.py` - cobertura nueva para inicios canónicos de documentos.
- `python-services/ai-proveedores/tests/unit/test_estados_proveedor.py` - taxonomía post-registro actualizada.

## Decisions Made
- `awaiting_menu_option` se mantuvo intacto porque sigue siendo checkpoint compartido fuera del boundary de maintenance.
- Los aliases legacy internos de maintenance se eliminaron solo donde el runtime de maintenance ya no los emite.
- No toqué `review` ni `availability`; cualquier compatibilidad pendiente fuera de maintenance debe resolverse en sus propios workers.

## Patterns/Learnings for Next Tasks
- Los estados de maintenance que sí conviene tratar como compartidos son los que pasan por `MENU_POST_REGISTRO_STATES`; al cambiar ahí, availability los hereda automáticamente vía import.
- `experience_step.py` tenía un bug latent e independiente del rename: el payload de redes requiere `facebook_username` e `instagram_username`.
- Los módulos renombrados no requieren aliases de archivo si todos los imports del boundary de maintenance se actualizan juntos.

## TDD Verification
- [x] Tests written BEFORE implementation
- [x] Each test failed first (RED), then passed (GREEN)
- [x] Tests run: `pytest -q python-services/ai-proveedores/tests/unit/test_router_maintenance_menu.py python-services/ai-proveedores/tests/unit/test_router_maintenance_info.py python-services/ai-proveedores/tests/unit/test_router_maintenance_deletion.py python-services/ai-proveedores/tests/unit/test_router_maintenance_social.py python-services/ai-proveedores/tests/unit/test_document_update.py python-services/ai-proveedores/tests/unit/test_estados_proveedor.py` -> `32 passed`
- [x] Refactoring kept tests green

## Code Quality (if qlty available)
- Issues found: 0 specific to maintenance in the targeted test pass
- Issues auto-fixed: 0
- Remaining issues: No se ejecutó `qlty`; no era necesario para este cambio localizado

## Issues Encountered
- `pytest -q python-services/ai-proveedores/tests/unit/test_normalizacion_servicios_ia.py` falla en colección por `ModuleNotFoundError: No module named 'services.availability.estados'`.
- Esa falla nace fuera del boundary de maintenance y no se tocó en esta tarea.

## Next Task Context
- Si otro worker va a completar la unificación global, el siguiente candidato natural es reemplazar `awaiting_menu_option` por una taxonomía más explícita, pero eso requiere coordinación con `review`, `availability`, `orquestacion_whatsapp` y rehidratación de sesiones.
