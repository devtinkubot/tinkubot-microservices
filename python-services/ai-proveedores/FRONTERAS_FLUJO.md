# Fronteras de `ai-proveedores`

Este documento separa los contextos de ejecución del servicio para poder refactorizar sin romper los flujos ya estabilizados.

## 1. Mapa actual

La arquitectura del servicio ya está separada por capas:

- `config/`: configuración y parámetros operativos.
- `models/`: contratos y modelos de dominio.
- `flows/`: orquestación y transiciones.
- `routes/`: fronteras explícitas por contexto.
- `services/`: lógica de negocio.
- `templates/`: copys y payloads visibles.
- `infrastructure/`: integraciones técnicas.
- `utils/`: helpers puros.
- `tools/`: operaciones manuales y batch.
- `tests/`: verificación automatizada.

`runtime` es una frontera conceptual, no una carpeta física obligatoria.

## 2. Onboarding

El alta inicial del proveedor vive en:

- `routes/onboarding/`
- `flows/onboarding/`
- `services/onboarding/`
- `templates/onboarding/`
- `templates/onboarding/registration/`

Este contexto cubre:

- captura de ciudad
- documentos
- experiencia
- servicios iniciales
- consentimiento final
- envío a revisión

## 3. Review

La revisión es la frontera entre alta y operación:

- `routes/review/`
- `services/review/`
- `templates/review/`

Este contexto cubre:

- estado `pending_verification`
- policy de silencio o reanudación
- entrada al menú limitado cuando aplica

## 4. Maintenance

El menú operativo del proveedor ya registrado vive en:

- `routes/maintenance/`
- `flows/maintenance/`
- `services/maintenance/`
- `templates/maintenance/`

Este contexto cubre:

- edición de perfil
- actualización de documentos
- redes sociales
- certificados
- eliminación de registro
- edición de servicios

## 5. Availability

La disponibilidad es un contexto separado y no forma parte del onboarding:

- `routes/availability/`
- `services/availability/`

Este contexto cubre:

- respuesta del proveedor a una solicitud entrante
- procesamiento Redis de la respuesta
- reanudación a menú o salida

## 6. Sesión y mensajes compartidos

Los mensajes comunes ya no viven aislados por flujo:

- `templates/shared/mensajes_sesion.py`
- `templates/shared/mensajes_interaccion.py`
- `services/shared/normalizacion_respuestas.py`

## 7. Compatibilidad y legado

Estos módulos siguen vivos porque todavía hay rutas o tests que los referencian. No se deben borrar sin una pasada de compatibilidad:

- `flows/maintenance/document_update.py`
- `flows/maintenance/wait_experience.py`
- `flows/maintenance/wait_social.py`
- `flows/maintenance/wait_name.py`
- `flows/maintenance/services_confirmation.py`
- `flows/maintenance/confirmation.py`
- `tests/unit/test_document_update.py`
- `tests/unit/test_consentimiento_interactive.py`

`wait_social.py` sigue siendo un puente de perfil y completado post-alta, no un paso de onboarding puro.

## 8. Qué no debe volver a mezclarse

- `flows/` no debe recuperar copys inline de usuario.
- `templates/` no debe depender de lógica de orquestación.
- `services/shared/` debe ser la fuente única de reglas comunes de interacción.
- `infrastructure/` no debe volver a pedir prestadas reglas del dominio.

## 9. Candidatos a limpieza futura

Cuando no queden consumidores legacy, se puede revisar:

- si `templates/consentimiento/*` todavía aporta valor
- si `FLUJO_SISTEMA.md` sigue siendo necesario o basta este mapa
- si los puentes de compatibilidad restantes pueden retirarse sin afectar sesiones activas
