# Flujo del Sistema de `ai-proveedores`

## Objetivo
Este documento describe el onboarding actual de proveedores. El menú del proveedor se maneja por separado y no forma parte de este flujo.

## Piezas Principales

- `principal.py`: recibe el webhook de WhatsApp y delega al router.
- `flows/router.py`: decide el estado actual y enruta cada mensaje.
- `services/sesion_proveedor.py`: sincroniza estado de Redis con el perfil guardado.
- `flows/constructors/`: construye payloads y respuestas reutilizables.
- `flows/session/`: gestiona la sesión conversacional y el perfil.
- `flows/validators/`: valida y normaliza entrada.
- `flows/maintenance/`: contiene los handlers operativos del menú y mantenimiento del proveedor.
- `templates/onboarding/`: contiene la tarjeta inicial, la solicitud de ciudad, los documentos y la experiencia del onboarding.
- `templates/onboarding/registration/`: contiene copies y payloads del cierre de onboarding y compatibilidad de alta.
- `templates/review/`: mensajes cuando el registro queda en revisión.
- `templates/maintenance/`: menús y copys de mantenimiento del proveedor.
- `templates/shared/`: componentes y mensajes transversales del proveedor.
- `templates/shared/mensajes_sesion.py`: mensajes de timeout, reinicio y reanudación de sesión.

## Flujo Actual de Onboarding

```text
1. Mensaje inicial + botón Registrarse
2. Ubicación
3. Foto frontal de cédula
4. Foto de perfil
5. Selección de años de experiencia
6. Servicio 1
7. Servicio 2
8. Servicio 3
9. Consentimiento final con resumen breve
10. Confirmación de registro en revisión
```

## Detalle por Paso

1. `Registrarse`
   - Abre el alta del proveedor desde una tarjeta de bienvenida con imagen.

2. `Ubicación`
   - El usuario puede compartir GPS o escribir su ciudad manualmente.
   - La tarjeta de solicitud vive en `templates/onboarding/ciudad.py`.

3. `Foto frontal de cédula`
   - Se captura la cédula frontal para extraer el nombre y validar el documento.
   - La tarjeta de onboarding vive en `templates/onboarding/documentos.py`.

4. `Foto de perfil`
   - Se solicita una imagen clara del rostro para el perfil público.
   - La tarjeta de onboarding vive en `templates/onboarding/documentos.py`.

5. `Años de experiencia`
   - Se presenta como lista interactiva.
   - El payload vive en `templates/onboarding/experiencia.py`.

6. a 8. `Servicios`
   - El usuario escribe hasta 3 servicios.
   - Los ejemplos pueden venir de Supabase, pero solo como apoyo visual.

9. `Consentimiento final`
   - Se muestra un resumen breve.
   - El usuario confirma con `Aceptar` o corrige con `Cancelar`.

10. `Revisión`
   - El registro queda enviado y el proveedor pasa a revisión.

## Estados Relevantes

- `awaiting_menu_option`
- `awaiting_city`
- `maintenance_name`
- `onboarding_face_photo`
- `awaiting_experience`
- `awaiting_specialty`
- `awaiting_services_confirmation`
- `maintenance_profile_completion_confirmation`
- `awaiting_consent`
- `pending_verification`

## Notas

- El consentimiento ya no se usa como primer paso del onboarding.
- El menú del proveedor queda fuera de este flujo para poder evolucionarlo de forma independiente.
- Los flujos de actualización de perfil siguen existiendo, pero no forman parte del onboarding nuevo.
- Los menús operativos y los copys de mantenimiento viven en `templates/maintenance/`.
