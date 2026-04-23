# Fronteras de `ai-proveedores`

Este documento separa los contextos de ejecución del servicio para poder refactorizar sin romper los flujos ya estabilizados.

## 1. Mapa actual

La arquitectura del servicio ya está separada por capas:

- `config/`: configuración y parámetros operativos.
- `models/`: contratos y modelos de dominio.
- `flows/`: orquestación y transiciones.
- `principal.py`: punto de entrada de la aplicación FastAPI.
- `services/`: lógica de negocio.
- `templates/`: copys y payloads visibles.
- `infrastructure/`: integraciones técnicas.
- `utils/`: helpers puros.
- `tools/`: operaciones manuales y batch.
- `tests/`: verificación automatizada.

`runtime` es una frontera conceptual, no una carpeta física obligatoria.

## 2. Onboarding

El alta inicial del proveedor vive en:

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

- `flows/review/`
- `services/review/`
- `templates/review/`

Este contexto cubre:

- estado `pending_verification`
- policy de silencio o reanudación
- entrada al menú limitado cuando aplica

## 4. Maintenance

El menú operativo del proveedor ya registrado vive en:

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

- `flows/availability/`
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

`services/shared/` es una zona de transición y soporte técnico. No debe usarse
para mover reglas de negocio que pertenezcan a un solo contexto.

## 7. Compatibilidad y legado

Estos módulos siguen vivos porque todavía hay tests o consumidores históricos que los referencian. No se deben borrar sin una pasada de compatibilidad:

- `flows/maintenance/document_update.py`
- `flows/maintenance/certificate_step.py` (antes `wait_certificate.py`)
- `flows/maintenance/experience_step.py` (antes `wait_experience.py`)
- `flows/maintenance/social_step.py` (antes `wait_social.py`)
- `flows/maintenance/name_step.py` (antes `wait_name.py`)
- `flows/maintenance/services_confirmation.py`
- `flows/maintenance/confirmation.py`
- `tests/unit/test_document_update.py`
- `tests/unit/test_consentimiento_interactive.py`

`social_step.py` sigue siendo un puente de perfil y completado post-alta, no un paso de onboarding puro.

### Estados canónicos actuales

Los estados que hoy se consideran vivos y con sentido de negocio son:

- administrativos: `pending`, `approved`, `rejected`
- revisión / corte de alta: `pending_verification`
- salida operativa / menú: `awaiting_menu_option`
- onboarding: `onboarding_consent`, `onboarding_city`, `onboarding_dni_front_photo`, `onboarding_face_photo`, `onboarding_experience`, `onboarding_specialty`, `onboarding_add_another_service`, `onboarding_social_media`, `onboarding_real_phone`

Todo estado fuera de esa lista debe tratarse como alias legacy, puente temporal o dato histórico a limpiar en Supabase.

## 8. Qué no debe volver a mezclarse

- `flows/` no debe recuperar copys inline de usuario.
- `templates/` no debe depender de lógica de orquestación.
- `services/shared/` debe limitarse a compatibilidad y utilidades técnicas.
- ninguna regla que cambie por ownership de `onboarding`, `maintenance`,
  `review` o `availability` debe vivir allí.
- `infrastructure/` no debe volver a pedir prestadas reglas del dominio.

## 9. Candidatos a limpieza futura

Cuando no queden consumidores legacy, se puede revisar:

- si `templates/consentimiento/*` todavía aporta valor
- si `FLUJO_SISTEMA.md` sigue siendo necesario o basta este mapa
- si los puentes de compatibilidad restantes pueden retirarse sin afectar sesiones activas
