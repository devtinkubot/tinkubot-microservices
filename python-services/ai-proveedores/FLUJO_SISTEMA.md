# Flujo del Sistema de `ai-proveedores`

## Objetivo
Este documento describe el recorrido operativo del servicio con la arquitectura actual. El onboarding, la revisión, el mantenimiento y la disponibilidad ya tienen fronteras separadas.

## Entrada principal

- `principal.py`: recibe el webhook de WhatsApp y delega al router principal.
- `flows/router.py`: decide el contexto y reenvía cada mensaje.

## Capas de ejecución

- `routes/onboarding/`: entrada explícita al alta del proveedor.
- `routes/review/`: control del estado de revisión y reanudación.
- `routes/maintenance/`: menú operativo del proveedor registrado.
- `routes/availability/`: respuesta a solicitudes de disponibilidad.
- `flows/onboarding/`: transición interna del alta.
- `flows/maintenance/`: transición y orquestación del menú operativo.
- `services/onboarding/`: lógica de alta y persistencia asociada.
- `services/review/`: policy, mensajes y estado de revisión.
- `services/maintenance/`: lógica de negocio post-alta.
- `services/availability/`: procesamiento de disponibilidad.
- `services/shared/`: reglas compartidas de interacción y prompts de IA.
- `templates/`: copys y payloads visibles.
- `infrastructure/`: Redis, Supabase, OpenAI y storage.

## Flujo de alto nivel

```text
1. WhatsApp -> principal.py
2. principal.py -> flows/router.py
3. Router decide entre onboarding, review, maintenance o availability
4. Cada contexto usa su route, flow, service y templates correspondientes
5. Los mensajes visibles salen desde templates/
6. Las reglas compartidas salen desde services/shared/
```

## Onboarding

El alta inicial vive en:

- `routes/onboarding/router.py`
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
5. Años de experiencia.
6. Servicios del proveedor.
7. Consentimiento final.
8. Envío a revisión.

## Review

La revisión vive en:

- `routes/review/router.py`
- `services/review/state.py`
- `services/review/messages.py`
- `templates/review/`

Responsabilidades:

- mantener `pending_verification`
- decidir respuesta, silencio o reanudación
- derivar al menú limitado cuando corresponde

## Maintenance

El menú operativo vive en:

- `routes/maintenance/router.py`
- `routes/maintenance/info.py`
- `routes/maintenance/deletion.py`
- `routes/maintenance/handlers/`
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

## Availability

La disponibilidad vive en:

- `routes/availability/router.py`
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
- `services/shared/` es la fuente de verdad para reglas comunes y prompts.
- `infrastructure/` queda para integraciones técnicas, no para policy de negocio.
