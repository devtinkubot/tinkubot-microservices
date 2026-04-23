# Flujo del Sistema de `ai-proveedores`

## Objetivo
Este documento describe el recorrido operativo del servicio con la arquitectura actual. El onboarding, la revisión, el mantenimiento y la disponibilidad ya tienen fronteras separadas.

## Entrada principal

- `principal.py`: recibe el webhook de WhatsApp y delega al router principal.
- `flows/router.py`: decide el contexto y reenvía cada mensaje.

## Capas de ejecución

- `flows/onboarding/`: transición interna del alta.
- `flows/maintenance/`: transición y orquestación del menú operativo.
- `flows/review/`: control del estado de revisión y reanudación.
- `flows/availability/`: respuesta a solicitudes de disponibilidad.
- `services/onboarding/`: lógica de alta y persistencia asociada.
- `services/review/`: policy, mensajes y estado de revisión.
- `services/maintenance/`: lógica de negocio post-alta.
- `services/availability/`: procesamiento de disponibilidad.
- `services/shared/`: utilidades técnicas, compatibilidad temporal y
  normalizaciones mecánicas.
- `templates/`: copys y payloads visibles.
- `infrastructure/`: Redis, Supabase, OpenAI y storage.

## Flujo de alto nivel

```text
1. WhatsApp -> principal.py
2. principal.py -> flows/router.py
3. Router decide entre onboarding, review, maintenance o availability
4. Cada contexto usa su flow, service y templates correspondientes
5. Los mensajes visibles salen desde templates/
6. Las utilidades técnicas salen desde `services/shared/`; las reglas de
   negocio viven en el contexto dueño.
7. El paso de servicios publica un evento crudo a Redis y deja la normalización/persistencia al worker async
```

## Onboarding

El alta inicial vive en:

- `flows/onboarding/router.py`
- `flows/onboarding/handlers/`
- `services/onboarding/`
- `templates/onboarding/`
- `templates/onboarding/registration/`

Pasos principales:

1. Bienvenida y arranque del registro.
2. Ciudad o ubicación.
3. Cédula frontal.
4. Foto de perfil.
5. Experiencia como `experience_range`.
6. Servicios del proveedor.
7. Consentimiento final.
8. Envío a revisión.

Regla operativa:

- Cada paso normaliza su entrada antes de persistirla.
- Consentimiento solo avanza con el botón interactivo de aceptar; texto libre o rechazos se reemiten como solicitud de consentimiento.
- `real_phone` solo se deriva automáticamente en consentimiento cuando el `phone` observado es un JID numérico usable (`...@s.whatsapp.net`).
- Si no hay un JID numérico usable, `real_phone` se pide explícitamente después de consentimiento.
- `@lid` y `user_id`/BSUID son identidades de continuidad, no teléfonos humanos.
- Al final del flujo solo se ajusta el estado del proveedor y el checkpoint duradero; no se reinterpreta identidad.
- El paso de servicios no hace el trabajo pesado en el request path: solo captura el texto crudo y deja la resolución y la persistencia final al worker.
- La experiencia se lee y muestra como `experience_range`; el entero histórico ya no forma parte del contrato vivo.

## Review

La revisión vive en:

- `flows/review/router.py`
- `services/review/state.py`
- `services/review/messages.py`
- `templates/review/`

Responsabilidades:

- mantener `pending_verification`
- decidir respuesta, silencio o reanudación
- derivar al menú limitado cuando corresponde

## Maintenance

El menú operativo vive en:

- `flows/maintenance/`
- `services/maintenance/`
- `templates/maintenance/`

Responsabilidades:

- edición de perfil
- edición de servicios
- actualización de documentos
- redes sociales
- certificados
- eliminación de registro
- navegación de menú

Regla operativa:

- si una pantalla muestra experiencia, debe usar `experience_range`
- el flujo de mantenimiento no debe reintroducir `experience_years` como fuente de verdad

## Availability

La disponibilidad vive en:

- `flows/availability/router.py`
- `services/availability/processor.py`
- `services/availability/disponibilidad_admin.py`

Responsabilidades:

- capturar la respuesta del proveedor
- normalizar la interacción
- reanudar o salir al menú principal

## Sesión y mensajes compartidos

- `templates/shared/mensajes_sesion.py`: reinicio, timeout y reanudación.
- `templates/shared/mensajes_interaccion.py`: copys comunes de interacción.
- `services/shared/normalizacion_respuestas.py`: interpretaciones compartidas de texto.
- `services/shared/prompts_ia.py`: builders de prompts y mensajes IA.

## Estado de la arquitectura

El servicio ya no depende de una sola carpeta monolítica para todo el flujo.
La separación actual es:

- `utils/` para helpers puros
- `tools/` para procesos manuales o batch
- `tests/` para validación
- `runtime` como concepto arquitectónico, no como carpeta

## Notas

- `flows/` no debe volver a acumular texto visible hardcodeado.
- `templates/` es la fuente de verdad para el copy.
- `services/shared/` no es un dominio común: solo debe contener soporte
  técnico y compatibilidad temporal.
- `infrastructure/` queda para integraciones técnicas, no para policy de negocio.
