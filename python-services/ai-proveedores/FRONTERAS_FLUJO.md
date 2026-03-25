# Fronteras de `ai-proveedores`

Este documento separa el flujo de onboarding del menú operativo del proveedor para poder limpiar código con seguridad.

## 1. Onboarding activo

Estos archivos forman parte del alta de proveedores y deben mantenerse juntos:

- `templates/onboarding/inicio.py`
- `templates/onboarding/ciudad.py`
- `templates/onboarding/documentos.py`
- `templates/onboarding/experiencia.py`
- `templates/onboarding/consentimiento.py`
- `templates/onboarding/caducidad.py`
- `templates/onboarding/telefono.py`
- `flows/onboarding/router.py`
- `flows/onboarding/handlers/ciudad.py`
- `flows/onboarding/handlers/documentos.py`
- `flows/onboarding/handlers/experiencia.py`
- `flows/onboarding/handlers/real_phone.py`
- `flows/onboarding/handlers/servicios.py`
- `flows/onboarding/handlers/consentimiento.py`
- `routes/onboarding/router.py`
- `flows/router.py`
- `services/sesion_proveedor.py`
- `templates/review/estados.py`

## 2. Menú del proveedor

Estos archivos son del menú operativo ya registrado y deben evolucionar aparte:

- `templates/maintenance/menus.py`
- `templates/maintenance/actualizacion_perfil.py`
- `templates/maintenance/eliminacion_registro.py`
- `flows/constructors/menu.py`
- `flows/constructors/verification.py`
- `flows/maintenance/menu.py`
- `flows/maintenance/services.py`
- `tests/unit/test_servicios_submenus.py`

## 3. Disponibilidad

La disponibilidad queda separada del onboarding y del menú del proveedor:

- `services/availability/processor.py`
- `services/availability/disponibilidad_admin.py`
- `tests/unit/test_principal_disponibilidad.py`

## 4. Sesión y reanudación

La sesión ya no tiene carpeta propia en `templates/`; sus mensajes son compartidos:

- `templates/shared/mensajes_sesion.py`
- `flows/router.py`

## 5. Compatibilidad y legado

Estos módulos siguen vivos porque aún existen rutas, fallbacks o tests que los usan. No se deben borrar todavía:

- `flows/maintenance/document_update.py`
- `flows/maintenance/wait_experience.py`
- `flows/maintenance/wait_social.py`
- `flows/maintenance/wait_name.py`
- `flows/maintenance/services_confirmation.py`
- `flows/maintenance/confirmation.py`
- `tests/unit/test_document_update.py`
- `tests/unit/test_consentimiento_interactive.py`

`wait_social.py` sigue vivo como flujo de perfil y completado post-alta, no como onboarding.

## 6. Candidatos a limpieza futura

Cuando el menú del proveedor deje de depender de la compatibilidad de estados de disponibilidad, se puede revisar si ya no hace falta:

- mantener `templates/consentimiento/*` si ya no hay estados que entren a `awaiting_consent`
- conservar `FLUJO_SISTEMA.md` solo si sirve como documentación complementaria
