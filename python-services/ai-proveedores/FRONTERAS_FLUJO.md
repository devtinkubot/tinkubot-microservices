# Fronteras de `ai-proveedores`

Este documento separa el flujo de onboarding del menú operativo del proveedor para poder limpiar código con seguridad.

## 1. Onboarding activo

Estos archivos forman parte del alta de proveedores y deben mantenerse juntos:

- `templates/onboarding/inicio.py`
- `templates/registro/pasos_registro.py`
- `templates/onboarding/ciudad.py`
- `templates/onboarding/documentos.py`
- `templates/onboarding/experiencia.py`
- `templates/registro/documentacion.py`
- `templates/registro/perfil_profesional.py`
- `templates/registro/servicios.py`
- `templates/registro/confirmacion.py`
- `templates/registro/resumen_consentimiento.py`
- `flows/gestores_estados/gestor_documentos.py`
- `flows/gestores_estados/gestor_espera_nombre.py`
- `flows/gestores_estados/gestor_espera_experiencia.py`
- `flows/gestores_estados/gestor_confirmacion_servicios.py`
- `flows/gestores_estados/gestor_confirmacion.py`
- `flows/router.py`
- `services/sesion_proveedor.py`
- `templates/verificacion/estados.py`

## 2. Menú del proveedor

Estos archivos son del menú operativo ya registrado y deben evolucionar aparte:

- `templates/interfaz/menus.py`
- `flows/constructores/construidor_menu.py`
- `flows/constructores/construidor_verificacion.py`
- `flows/gestores_estados/gestor_menu.py`
- `flows/gestores_estados/gestor_servicios.py`
- `tests/unit/test_servicios_submenus.py`
- `tests/unit/test_menu_limitado_revision.py`

## 3. Disponibilidad

La disponibilidad queda separada del onboarding y del menú del proveedor:

- `services/disponibilidad_interceptacion.py`
- `services/disponibilidad_admin.py`
- `tests/unit/test_principal_disponibilidad.py`

## 4. Compatibilidad y legado

Estos módulos siguen vivos porque aún existen rutas, fallbacks o tests que los usan. No se deben borrar todavía:

- `templates/consentimiento/mensajes.py`
- `flows/consentimiento/*`
- `flows/constructores/construidor_consentimiento.py`
- `flows/gestores_estados/gestor_consentimiento.py`
- `tests/unit/test_consentimiento_interactive.py`
- `tests/unit/test_dedupe_media.py`

## 5. Candidatos a limpieza futura

Cuando el menú del proveedor deje de depender de compatibilidad temporal, se puede revisar si ya no hace falta:

- mantener `templates/consentimiento/*` si ya no hay estados que entren a `awaiting_consent`
- conservar `FLUJO_SISTEMA.md` solo si sirve como documentación complementaria
