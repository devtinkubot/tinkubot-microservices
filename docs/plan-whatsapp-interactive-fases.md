# Plan Maestro: WhatsApp Onboarding Precontractual (Session-First + Ubicación)

## Resumen
Este plan define el flujo objetivo de TinkuBot usando WhatsApp Cloud API con onboarding precontractual en modo **session-first** (sin template marketing para onboarding inicial).

Flujos objetivo obligatorios:
- Cliente Nuevo (session-first): mensaje único interactive (`header image + body + botón Continuar`) -> ubicación/ciudad -> problema -> confirmación IA -> búsqueda asíncrona.
- Cliente Activo: problema -> confirmación IA -> búsqueda asíncrona.

Principio clave:
- La búsqueda de proveedores ocurre en segundo plano y no bloquea la interacción inmediata.

## Restricción operativa (ventana de 24h)
- Flows, botones, listas, texto libre y solicitud de ubicación aplican cuando la conversación está abierta por mensaje reciente del usuario.
- Política vigente de costo: **no iniciar conversación fuera de ventana para onboarding**.
- Si negocio decide reactivar envíos proactivos en el futuro, se reintroduce plantilla aprobada para apertura fuera de 24h.

## Decisión vigente (2026-03-01)
- Estrategia por defecto: `WA_ONBOARDING_STRATEGY=session_first_v1`.
- Se evita template categoría Marketing para onboarding inicial.
- Fuera de sesión: no se envía onboarding automáticamente.

## Actualización aplicada (2026-03-02)
- Prompt inicial de servicio unificado a:
  - `*¿Qué necesitas resolver?*. Describe lo que necesitas.`
- Se eliminó la variante sin negrita:
  - `¿Qué necesitas resolver?. Describe lo que necesitas.`
- En transiciones a `awaiting_service` (consentimiento aceptado, ciudad confirmada, timeout/reset y fallbacks de enrutador), el payload debe incluir `ui.type="list"` para mostrar botón de lista.
- Se elimina uso activo de salida solo texto para este prompt en flujo vigente.

## Ownership de responsabilidades
- `ai-clientes`:
  - Lógica conversacional y máquina de estados.
  - Copy/mensajes de negocio.
  - Reglas funcionales de fallback.
- `wa-gateway`:
  - Adaptador de canal WhatsApp Cloud API.
  - Parseo inbound (`text`, `interactive`, `location`) incluyendo respuestas de Flow.
  - Serialización outbound según `ui.type`.
  - Fallback técnico mínimo cuando no se pueda enviar `ui`.

## Responsabilidades operativas (intervención externa)
- Usuario (externo al agente):
  - Ejecuta scripts/migraciones SQL en Supabase desde su editor/entorno con acceso.
  - Ejecuta validaciones en Meta/WABA cuando se requieran credenciales no disponibles para el agente.
- Agente:
  - Prepara scripts SQL, checklist y pasos exactos para ejecución externa.
  - Ejecuta validación local de código, contenedores y smoke tests.

## Invariantes obligatorios
1. Regla base: no transicionar a `searching` sin `confirm_service`, excepto cuando el servicio proviene de `interactive_list_reply` (selección explícita de lista popular).
2. Para onboarding nuevo session-first, el primer contacto debe salir en un único mensaje `buttons` con `header image`.
3. Si no hay ubicación persistida, el estado debe ser `awaiting_city` y se pide ubicación primero.
4. El fallback textual de ciudad/cantón solo aplica cuando no llega ubicación compartida.
5. Cliente activo válido: ubicación persistida (`lat/lng`) y/o ciudad confirmada derivada.
6. `continue_onboarding` (o fallback `continuar`) debe llevar a `awaiting_city` sin reemitir onboarding.

## Modelo de datos y persistencia

### Source of truth de perfil
Tabla: `public.customers`

Estado actual relevante:
- `id`, `phone_number`, `city`, `city_confirmed_at`, `has_consent`, `notes`, `created_at`, `updated_at`.

Cambios requeridos:
- Agregar `location_lat numeric null`.
- Agregar `location_lng numeric null`.
- Agregar `location_updated_at timestamptz null`.

Uso:
- `customers` define estado de cliente (nuevo/activo).
- `city` se guarda normalizada desde ubicación o fallback textual.

### Source of truth de solicitudes
Tabla principal: `public.customer_service_requests`

Uso:
- Cada nueva búsqueda debe registrarse aquí.
- `city_snapshot` se llena desde `customers.city`.
- `metadata` puede guardar coordenadas de la solicitud (`lat/lng`) para trazabilidad.

### Tabla legacy
Tabla: `public.service_requests`

Uso:
- Mantener temporalmente por compatibilidad/histórico.
- No usarla como tabla principal del flujo nuevo.

## Contratos e interfaces

### Meta -> wa-gateway (inbound)
Soportar:
- `text`
- `interactive.button_reply`
- `interactive.list_reply` (reservado)
- `interactive.nfm_reply` (respuestas de Flow)
- `location`

### wa-gateway -> AI Service (payload entrante)
```json
{
  "from_number": "5939...@s.whatsapp.net",
  "content": "texto libre (vacío cuando message_type=interactive_*)",
  "message_type": "text | interactive_button_reply | interactive_list_reply | interactive_flow_reply | location",
  "selected_option": "problem_confirm_yes",
  "flow_payload": {
    "consent_accepted": true,
    "city": "Cuenca"
  },
  "location": {
    "latitude": -0.18,
    "longitude": -78.47,
    "name": "Mi ubicación",
    "address": "..."
  },
  "account_id": "bot-clientes"
}
```

Compatibilidad:
- Para `interactive_button_reply` y `interactive_list_reply`, backend procesa `selected_option` como source of truth.
- Para `interactive_flow_reply`, backend procesa `flow_payload` como source of truth.
- `content` se mantiene para `text/location` y llega vacío para `interactive_*` para evitar duplicidad semántica.

### AI Service -> wa-gateway (respuesta)
```json
{
  "response": "¿Confirmas este problema?",
  "ui": {
    "type": "buttons",
    "id": "problem_confirmation_v1",
    "options": [
      { "id": "problem_confirm_yes", "title": "Sí, correcto" },
      { "id": "problem_confirm_no", "title": "No, corregir" }
    ]
  }
}
```

Solicitud de ubicación:
```json
{
  "response": "Comparte tu ubicación para ubicar proveedores cercanos.",
  "ui": {
    "type": "location_request",
    "id": "request_location_v1"
  }
}
```

Onboarding precontractual por plantilla:
```json
{
  "response": "",
  "ui": {
    "type": "template",
    "id": "onboarding_precontractual_v1",
    "template_name": "tinkubot_onboarding_precontractual_v1",
    "template_language": "es",
    "template_components": [
      {
        "type": "header",
        "parameters": [
          {
            "type": "image",
            "image": { "link": "https://example.com/logo.png" }
          }
        ]
      }
    ]
  }
}
```

Onboarding session-first (vigente):
```json
{
  "messages": [
    {
      "response": "*TinkuBot*\n\nPara buscar expertos cercanos. Usaré:\n\n* Tu teléfono\n* Ciudad o ubicación\n* Necesidad o Problema a resolver",
      "ui": {
        "type": "buttons",
        "id": "onboarding_continue_v1",
        "header_type": "image",
        "header_media_url": "https://cdn.tu-dominio.com/tinkubot/onboarding.png",
        "options": [
          { "id": "continue_onboarding", "title": "Continuar" }
        ]
      }
    }
  ]
}
```

## Estado general por fases
| Fase | Nombre | Estado |
|---|---|---|
| 0 | Invariantes, contrato y modelo de datos | `completed` |
| 0B | Cambio de estrategia a session-first (sin template marketing) | `in_progress` |
| 1 | Inbound/Outbound interactive en `wa-gateway` | `in_progress` |
| 2 | Enrutamiento estricto Nuevo vs Activo en `ai-clientes` | `in_progress` |
| 3 | Solicitud de ubicación primero + fallback textual | `in_progress` |
| 4 | Confirmación IA obligatoria del problema | `completed` |
| 5 | Breakpoint y búsqueda asíncrona | `pending` |
| 6 | Hardening y observabilidad | `pending` |

## Gate Meta por fase (validación progresiva)
### Precheck único (antes de Fase 1)
- [ ] Webhook verify token y app secret válidos.
- [ ] Mapping `phone_number_id -> account` correcto.
- [ ] Cuenta objetivo habilitada en allowlist/flags.
- [x] Plantilla de apertura fuera de 24h aprobada en Meta: `tinkubot_politica_privacidad_v1`.

### Gate Fase 1
- [x] Inbound real validado: `text`, `interactive.button_reply`, `location`.
- [x] Outbound real validado: `buttons`, `location_request`.
- [ ] Outbound media validado: `image` (`media_url/media_type/media_caption`) en Meta.
- [ ] Inbound/Outbound Flow validado: `interactive.nfm_reply` + `ui.type=flow`.
- [x] Outbound payload validado sin `context/reply_to` forzado desde backend.
- [x] Evidencia registrada sobre comportamiento visual de reply en WhatsApp Web vs payload real.
  Nota: el reply visual observado corresponde a render del cliente WhatsApp Web; backend envía `has_context=false`.

### Gate Fase 0B (Session-first)
- [x] Definir política de costo y ventana: no onboarding proactivo fuera de sesión.
- [ ] `WA_ONBOARDING_STRATEGY=session_first_v1` habilitado en runtime.
- [ ] Primer contacto nuevo envía mensaje único `buttons` con `header image` + `Continuar`.
- [ ] `Continuar` avanza a `location_request` (payload o fallback por título).
- [ ] Verificación E2E real en número productivo.

### Gate Fase 3
- [x] Ubicación compartida llega en payload y mapea correctamente a `location`.
- [x] Caso real `lat/lng` sin `address/name` resuelve ciudad sin pedir texto.
- [x] Evidencia runtime de `geocode_provider_call|geocode_cache_hit` + `geocode_city_resolved`.
- [x] Si falla geocoding tras reintento, fallback textual controlado y trazado en logs.
  Nota: no se presentó timeout en la corrida real; fallback queda cubierto por implementación + tests.
- [x] Cierre operativo completado según subplan Fase 3A.

### Gate Fase 4
- [x] `confirm_service` es obligatorio y no existe bypass a `searching`.
  Evidencia: `tests/unit/test_enrutador_city_first.py::test_estado_vacio_con_ciudad_pasa_por_confirm_service_y_no_busca_directo`.

### Gate Fase 5
- [ ] Breakpoint responde inmediato.
- [ ] Búsqueda async notifica resultados luego.

## Verificación de despliegue por paso (obligatoria)
- Al cerrar cada paso del plan, se debe reconstruir y recrear el/los contenedores de los servicios intervenidos.
- Política estándar por paso:
  1. `docker compose build <servicio>`
  2. `docker compose up -d --force-recreate <servicio>`
  3. `docker compose ps <servicio>`
  4. Validar `health`/smoke test del paso.
- Política de caché:
  - Estándar: usar `--no-cache` solo cuando cambian dependencias, Dockerfile/base image, o hay sospecha de caché inconsistente.
  - Estricto opcional: usar `docker compose build --no-cache <servicio>` en todos los pasos.
- Un paso no se considera cerrado sin:
  - rebuild + recreate,
  - estado `Up`/`healthy`,
  - evidencia funcional mínima.

### Checklist reusable por paso
- [ ] Imagen reconstruida del servicio afectado.
- [ ] Contenedor recreado con `--force-recreate`.
- [ ] `docker compose ps` verificado.
- [ ] Health/smoke test ejecutado.
- [ ] Evidencia registrada en notas del paso.

### Evidencia mínima requerida por fase
- Fase 0B: logs con onboarding sin template + transición por `continue_onboarding`.
- Fase 1: payload/log outbound + validación interactivos reales.
- Fase 3: chat real con ubicación por pin + logs `geocode_*` + estado final del flujo.
- Fase 4: evidencia de transición obligatoria por `confirm_service`.
- Fase 5: evidencia de respuesta inmediata + búsqueda asíncrona posterior.

## Implementación de Session-first (Fase 0B)
### Objetivo
Reducir costo de conversación de onboarding eliminando template marketing en arranque normal.

### Alcance técnico
- `ai-clientes`:
  - Nuevo modo `session_first_v1`.
  - Onboarding inicial devuelve un único mensaje `buttons` con:
    - body de texto de onboarding.
    - `header_type=image` + `header_media_url`.
    - botón `Continuar` (`id=continue_onboarding`).
- `wa-gateway`:
  - Soporte outbound para header en interactive buttons (`header_type`, `header_media_url`).
  - Mantener soporte `buttons/location_request/flow/template`.
- Fallback de interacción:
  - Si `button_reply.id` viene vacío, usar `button_reply.title` normalizado (`continuar`).

### Variables de entorno (target)
- `WA_ONBOARDING_STRATEGY=session_first_v1`
- `WA_ONBOARDING_IMAGE_URL=<url_publica>`
- `WA_ONBOARDING_IMAGE_CAPTION=<opcional>`
- `WA_ONBOARDING_CONTINUE_LABEL=Continuar`
- `WA_ONBOARDING_TEMPLATE_*` queda como fallback/rollback, no como estrategia principal.

### QA / aceptación
- Nuevo usuario manda `hola`:
  - recibe un solo mensaje con imagen + texto + botón `Continuar`.
- Pulsa `Continuar`:
  - recibe solicitud de ubicación.
- Envía ubicación/ciudad:
  - recibe “¿Qué necesitas resolver?”.

## Fase 0: Invariantes, contrato y modelo de datos
### Objetivo
Dejar reglas de negocio y base de datos cerradas antes de implementar canal y flujo.

### Archivos a intervenir
- `docs/plan-whatsapp-interactive-fases.md`
- `python-services/ai-clientes/docs/*` (si aplica documentación interna)
- scripts/migraciones SQL del servicio de clientes (ruta del repositorio de migraciones vigente)

### Checklist técnico
- [x] Documentar invariantes obligatorios en diseño.
- [x] Definir migración SQL para `customers.location_lat/lng/location_updated_at`.
- [x] Declarar `customer_service_requests` como tabla principal de nuevas solicitudes.
- [x] Declarar `service_requests` como legacy temporal.
- [x] Confirmar intervención externa para ejecutar migración en Supabase (responsable: usuario).
- [x] Definir si ejecución de build será modo estándar o modo estricto (`--no-cache` siempre).  
  Decisión: modo estándar; `--no-cache` solo cuando cambian dependencias/base image o hay sospecha de caché inconsistente.
- [x] Registrar estado de precheck Meta.  
  Estado: pendiente de ejecución externa por usuario, bloqueante antes de iniciar Fase 1.

### Checklist QA
- [x] Validar que no hay ambigüedad de source of truth.
- [x] Validar compatibilidad de lectura con datos previos sin lat/lng.

### Cierre formal Fase 0 (2026-02-27)
- Scope cerrado:
  - Modelo de datos definido y aplicado para `customers.location_lat`, `customers.location_lng`, `customers.location_updated_at`.
  - Source of truth confirmado: `customers` para perfil, `customer_service_requests` para nuevas solicitudes.
- Evidencia técnica en `ai-clientes`:
  - Persistencia de ubicación implementada (`actualizar_ubicacion`) y lectura de `location_*`.
  - Limpieza de ubicación agregada al reset manual (`limpiar_ubicacion`).
- Evidencia de validación:
  - `pytest -q python-services/ai-clientes/tests/test_sesion_reset_regression.py python-services/ai-clientes/tests/contracts/test_repositorio_clientes_contract.py` -> `6 passed`.
- Evidencia operativa (runtime):
  - `docker compose build ai-clientes` -> imagen reconstruida (`tinkubot-microservices-ai-clientes`).
  - `docker compose up -d --force-recreate ai-clientes` -> contenedor recreado.
  - `docker compose ps ai-clientes` -> `Up ... (healthy)`.
  - `curl http://localhost:8001/health` -> `200` con `{"status":"healthy","redis":"connected","service":"ai-clientes"}`.
- Nota operativa:
  - El precheck Meta (token/app secret/mapping/allowlist) queda como validación externa obligatoria antes de Fase 1.

## Fase 1: Inbound/Outbound interactive en `wa-gateway`
### Objetivo
Transportar correctamente interacción y ubicación entre Meta y AI services.

### Archivos a intervenir
- `go-services/wa-gateway/internal/metawebhook/payload.go`
- `go-services/wa-gateway/internal/metawebhook/service.go`
- `go-services/wa-gateway/internal/webhook/types.go`
- `go-services/wa-gateway/internal/metaoutbound/client.go`
- `go-services/wa-gateway/internal/metawebhook/service_test.go`
- `go-services/wa-gateway/internal/metaoutbound/client_test.go`

### Checklist técnico
- [x] Parsear `interactive.button_reply` y `interactive.list_reply`.
- [x] Parsear `location` (lat/lng/name/address).
- [x] Extender payload a AI con `message_type`, `selected_option`, `location`.
- [x] Soportar outbound por `ui.type` (`buttons`, `location_request`).
- [x] Fallback a `text` cuando no exista `ui`.

### Checklist QA
- [x] Unit tests inbound para `text/button/location`.
- [x] Unit tests outbound para `buttons/location_request`.
- [ ] Test integración con payload real de Meta.

### Avance técnico Fase 1 (2026-02-27)
- Contrato webhook extendido (`message_type`, `selected_option`, `location`, `ui`).
- Parseo inbound Meta implementado para `text`, `interactive.button_reply`, `interactive.list_reply`, `location`.
- Outbound Meta implementado para:
  - texto (`type=text`)
  - botones (`type=interactive`, `interactive.type=button`)
  - solicitud de ubicación (`type=interactive`, `interactive.type=location_request_message`)
- Validación local:
  - `go test ./...` en `go-services/wa-gateway` -> OK.
- Evidencia operativa:
  - `docker compose build wa-gateway` -> OK.
  - `docker compose up -d --force-recreate wa-gateway` -> OK.
  - `docker compose ps wa-gateway` -> `healthy`.
  - `curl http://localhost:7000/health` -> `200` (`status=healthy`).

## Fase 2: Enrutamiento estricto Nuevo vs Activo (`ai-clientes`)
### Objetivo
Hacer cumplir flujo por perfil sin atajos.

### Archivos a intervenir
- `python-services/ai-clientes/flows/pre_enrutador.py`
- `python-services/ai-clientes/flows/enrutador.py`
- `python-services/ai-clientes/services/orquestador_conversacion.py`
- `python-services/ai-clientes/services/sesion_clientes.py`
- `python-services/ai-clientes/tests/test_pre_enrutador_regression.py`

### Checklist técnico
- [x] Nuevo sin ciudad/ubicación persistida -> onboarding session-first + `awaiting_city`.
- [ ] Cliente con ciudad/ubicación persistida -> `awaiting_service`.
- [ ] Activo completo -> `awaiting_service`.
- [ ] Eliminar atajo que permita iniciar búsqueda sin `confirm_service`.

### Checklist QA
- [ ] Casos de transición por perfil con cobertura.
- [ ] No regresión en reinicio y timeout de sesión.

### Subplan operativo Fase 2A: Onboarding session-first (interactive + continuar)
#### Objetivo operativo
- Reducir costo y fricción en el alta de cliente nuevo evitando plantilla de marketing en onboarding inicial, manteniendo continuidad directa al pedido de ubicación.

#### UX objetivo
- Mensaje inicial único `interactive buttons` con:
  - header con imagen de marca.
  - body con texto de onboarding.
  - botón `Continuar`.
- Al tocar `Continuar`: transición a `awaiting_city` con `location_request`.
- Luego: si hay ubicación/ciudad válida, transición a `awaiting_service` y prompt "¿Qué necesitas resolver?".

#### Alcance técnico
- `ai-clientes`:
  - Emisión de onboarding vía `ui.type=buttons` (`onboarding_continue_v1`) con `header_type=image`.
  - Parseo de quick reply `Continuar` (`selected_option=continue_onboarding|continuar|continue`) para pedir ubicación.
  - Compatibilidad temporal: mantener soporte inbound `interactive_flow_reply`.
- `wa-gateway`:
  - Soportar outbound `ui.type=buttons` con header (`interactive.header.type=image`).
  - Mantener parseo inbound `interactive.nfm_reply` y `flow_payload` por compatibilidad.

#### Checklist técnico
- [x] `solicitar_consentimiento` responde con `ui.type=buttons` + header image.
- [x] `wa-gateway` soporta outbound `ui.type=buttons` con header image.
- [x] `pre_enrutador` interpreta `Continuar` y responde con `location_request`.
- [ ] Mantener compatibilidad temporal de `interactive_flow_reply`.
- [ ] Mantener fallback textual de ciudad cuando no hay pin.

#### Checklist QA
- [ ] Caso real teléfono: onboarding muestra un solo mensaje con header imagen + body + `Continuar`.
- [ ] `Continuar` dispara solicitud de ubicación (`location_request_message`).
- [ ] Ubicación compartida avanza a "¿Qué necesitas resolver?".
- [ ] Fallback de ciudad por texto sigue funcionando.
- [ ] Evidencia en logs de `selected_option=continue_*` + `message_type=location` + transición de estado.

#### Criterio de cierre Fase 2A
- [ ] Onboarding session-first operativo en producción para clientes nuevos.
- [ ] Sin regresión de enrutamiento Nuevo vs Activo.
- [ ] Evidencia de chat real y logs anexada al plan.

## Fase 3: Solicitud de ubicación primero + fallback textual
### Objetivo
Capturar ubicación como ruta principal de UX.

### Archivos a intervenir
- `python-services/ai-clientes/flows/mensajes/mensajes_ubicacion.py`
- `python-services/ai-clientes/templates/mensajes/ubicacion.py`
- `python-services/ai-clientes/services/orquestador_conversacion.py`
- `python-services/ai-clientes/flows/manejadores_estados/manejo_ciudad.py`
- repositorio de persistencia de clientes (`python-services/ai-clientes/infrastructure/persistencia/*`)

### Checklist técnico
- [x] En `awaiting_city` emitir `ui.type=location_request`.
- [x] Si llega `message_type=location`, guardar `lat/lng`, resolver ciudad/cantón y persistir.
- [x] Actualizar `customers.city`, `city_confirmed_at`, `location_updated_at`.
- [x] Si no comparte ubicación, fallback a ciudad/cantón por texto.
- [x] Resolver ciudad desde `lat/lng` con reverse geocoding (Nominatim) cuando `address/name` no trae ciudad.
- [x] Cachear resolución de geocoding por coordenadas para reducir latencia/reintentos.
- [x] Reusar `city` confirmada del flujo en `awaiting_city` para no re-preguntar tras compartir ubicación.

### Checklist QA
- [ ] Flujo con ubicación compartida (incluyendo caso `lat/lng` sin `address/name`).
- [x] Flujo fallback textual.
- [ ] Persistencia correcta en BD (`customers`).
- [ ] Evidencia runtime de geocode hit/miss/fallback en logs.

### Avance técnico Fase 3 (2026-02-27)
- En `awaiting_city` ya se emite `ui.type=location_request` en:
  - `solicitar_ciudad()`
  - `solicitar_ciudad_con_servicio()`
  - cambio de ciudad desde `confirm_new_search`.
- Se mantiene fallback textual (usuario puede escribir ciudad sin compartir pin).
- Cobertura añadida:
  - `tests/unit/test_mensajes_ubicacion_ui.py` (2 casos).
  - `tests/unit/test_location_latlng_geocoding.py` (resolución desde coordenadas + no re-prompt en `awaiting_city`).

### Subplan operativo Fase 3A: Activación runtime de geocoding + validación real
#### Objetivo operativo
- Garantizar que la resolución de ciudad por `lat/lng` esté activa en runtime real (contenedor desplegado) y no solo en código.

#### Alcance
- Servicios: `ai-clientes`, `wa-gateway`.
- Flujo: consentimiento -> compartir ubicación por pin -> transición sin pedir ciudad textual.

#### Pasos obligatorios de ejecución
- [x] `docker compose build ai-clientes`
- [x] `docker compose up -d --force-recreate ai-clientes`
- [x] `docker compose build wa-gateway`
- [x] `docker compose up -d --force-recreate wa-gateway`
- [x] `docker compose ps ai-clientes wa-gateway` con estado `Up/healthy`
- [x] Smoke: `curl http://localhost:8001/health` y `curl http://localhost:7000/health`
  Nota: validado vía healthcheck Docker + logs internos `GET /health -> 200` post-recreate.

#### Prueba real obligatoria (teléfono)
- [x] Reset de sesión.
- [x] Aceptar consentimiento.
- [x] Compartir ubicación (mensaje `location`, sin texto de ciudad).
- [x] Verificar que NO aparezca “Indica la ciudad…” si geocoding resuelve ciudad.

#### Evidencia de logs obligatoria
- [x] En `ai-clientes`, presencia de al menos uno:
  - `geocode_provider_call`
  - `geocode_cache_hit`
- [x] En éxito:
  - `geocode_city_resolved`
- [x] En falla controlada:
  - `geocode_provider_timeout` + fallback textual explícito.
- [x] En `wa-gateway`:
  - log outbound con `has_context=false`.
  Nota: corrida real con éxito de geocode; condición de timeout queda cubierta en implementación y no fue necesaria en esta ejecución.

#### Criterio de cierre de Fase 3A
- [x] Caso real `lat/lng only` resuelto sin pedir ciudad textual.
- [x] Evidencia documentada (timestamp + logs + chat real).
- [x] Gate Fase 3 actualizado a completado.

#### Evidencia de ejecución Fase 3A (2026-02-27)
- `docker compose build ai-clientes wa-gateway` ejecutado OK.
- `docker compose up -d --force-recreate ai-clientes wa-gateway` ejecutado OK.
- `docker compose ps ai-clientes wa-gateway` -> ambos `Up (healthy)`.
- `docker inspect --format '{{.State.Health.Status}}'` en ambos contenedores -> `healthy`.

## Fase 4: Confirmación IA obligatoria del problema
### Objetivo
Validar entendimiento antes de disparar búsqueda.

### Archivos a intervenir
- `python-services/ai-clientes/flows/manejadores_estados/manejo_servicio.py`
- `python-services/ai-clientes/flows/manejadores_estados/manejo_confirmacion_servicio.py`
- `python-services/ai-clientes/flows/enrutador.py`
- `python-services/ai-clientes/templates/mensajes/validacion.py`

### Checklist técnico
- [x] `awaiting_service` siempre lleva a `confirm_service`.
- [x] Botones/entrada de confirmación: `problem_confirm_yes`, `problem_confirm_no`.
- [x] Confirmación negativa regresa a captura de problema.

### Checklist QA
- [x] Confirmación positiva inicia transición a búsqueda.
- [x] Confirmación negativa no inicia búsqueda.

### Avance técnico Fase 4 (2026-02-27 / 2026-03-02)
- `confirm_service` ahora emite botones interactivos con IDs estables:
  - `problem_confirm_yes`
  - `problem_confirm_no`
- Copy UX vigente en WhatsApp para confirmar servicio:
  - `¿Es este el servicio que buscas: *{servicio_obtenido_ia}*?`
  - Labels de botones: `Sí, correcto` y `No, corregir`.
  - Sin instrucción numérica `1/2` cuando hay botones interactivos.
- `manejo_confirmacion_servicio` acepta `selected_option` de interactive (`problem_confirm_yes/no`) además de texto/números.
- Reintento de confirmación inválida vuelve a enviar mensaje + `ui.buttons`.
- Prompt de `awaiting_service` migrado a lista interactiva (`ui.type=list`):
  - `¿Qué necesitas resolver?. Describe lo que necesitas.`
  - botón: `Ver servicios populares`
  - opciones: top 5 global últimos 30 días + `Otro servicio`.
  - fuente canónica vigente: `lead_events.service` (no `service_requests.profession`).
- Selección de lista (`interactive_list_reply`) con servicio popular:
  - omite `confirm_service` y transiciona directo a búsqueda.
- Selección `Otro servicio`:
  - mantiene `awaiting_service` y solicita texto libre.
- Cobertura añadida:
  - `tests/test_confirmacion_servicio_flag.py` (yes/no interactive + retry UI).
  - `tests/unit/test_manejo_servicio_necesidad_gate.py` valida `ui.buttons` al entrar a `confirm_service`.
  - `tests/unit/test_enrutador_city_first.py` valida `interactive_list_reply` (directo a búsqueda y ruta `Otro servicio`).
- Cierre de bypass (2026-02-28):
  - `flows/enrutador.py` ahora impide búsqueda directa cuando la conversación inicia sin estado y con ciudad.
  - El flujo pasa por `confirm_service` (set de `service_candidate` + `ui_confirmar_servicio`) antes de buscar.
  - Se agrega prueba de regresión en `tests/unit/test_enrutador_city_first.py`.

## Fase 5: Breakpoint y búsqueda asíncrona
### Objetivo
Responder rápido y ejecutar matching en segundo plano.

### Archivos a intervenir
- `python-services/ai-clientes/flows/busqueda_proveedores/coordinador_busqueda.py`
- `python-services/ai-clientes/flows/busqueda_proveedores/ejecutor_busqueda_en_segundo_plano.py`
- `python-services/ai-clientes/flows/busqueda_proveedores/transiciones_estados.py`

### Checklist técnico
- [ ] Definir punto de ruptura tras confirmación positiva.
- [ ] Responder inmediato: "Buscando... puede tardar hasta 2 minutos".
- [ ] Encolar/ejecutar búsqueda async y notificar resultados.
- [ ] Registrar solicitud en `customer_service_requests`.

### Checklist QA
- [ ] Tiempo de respuesta inicial bajo.
- [ ] Sin bloqueo de conversación por búsqueda.
- [ ] Persistencia de solicitud y estado final.

## Fase 6: Hardening y observabilidad
### Objetivo
Reducir regresiones y asegurar operación.

### Archivos a intervenir
- `go-services/wa-gateway/internal/metawebhook/service.go`
- `python-services/ai-clientes/services/sesiones/gestor_sesiones.py`
- `python-services/ai-clientes/tests/**`
- `go-services/wa-gateway/internal/**_test.go`

### Checklist técnico
- [ ] Idempotencia por `message_id`.
- [ ] Manejo robusto de duplicados/reintentos Meta.
- [ ] Alertas por caída de parseo interactive/location.
- [ ] KPIs: adopción ubicación, fallback rate, drop-off por estado.

### Checklist QA
- [ ] Suite de no regresión en `ai-clientes` y `wa-gateway`.
- [ ] Prueba E2E con número Meta real.

## Casos de prueba obligatorios
1. Nuevo sin ciudad/ubicación -> onboarding session-first en un único `buttons` (header imagen + texto + `Continuar`).
2. `Continuar` -> solicitud de ubicación (`location_request`) o ciudad por texto.
3. Ubicación compartida -> persistencia `lat/lng + ciudad`.
4. Sin ubicación compartida -> fallback textual.
5. Activo completo -> problema -> confirmación IA -> búsqueda async.
6. Verificación de invariante: ningún camino llega a `searching` sin `confirm_service`.
7. Respuesta inmediata en breakpoint y resultados posteriores.
8. Ubicación con solo coordenadas (`lat/lng`) no solicita ciudad textual si geocoding resuelve ciudad.
9. Si geocoding falla tras reintento, aplica fallback textual y no bloquea el flujo.
10. Verificar outbound Meta sin `context/reply_to` inyectado por backend.

## Decisiones cerradas
- Se usará onboarding session-first como estrategia principal para onboarding inicial (`ui.type=buttons` con header image + `Continuar`).
- La base legal operativa del onboarding es precontractual, sin consentimiento explícito en chat para primer contacto dentro de sesión iniciada por el usuario.
- La captura de ubicación compartida (`location_request`) se mantiene como paso operativo cuando aplique.
- Fallback textual se mantiene por resiliencia.
- `customers` es source of truth de perfil.
- `customer_service_requests` es source of truth de solicitudes nuevas.
- `service_requests` queda legacy temporal.
- Reverse geocoding para `lat/lng`: Nominatim + caché por coordenadas.
- Política de falla de geocoding: 1 reintento corto y luego fallback textual.

## Fuera de alcance actual (siguiente fase)
- Recordatorio proactivo 2 horas después para confirmar contratación y pedir calificación 1-5.
- Al ser proactivo, usará la plantilla aprobada `tinkubot_politica_privacidad_v1` cuando aplique.

## Registro de cambios
- Nota histórica:
  - Todo lo relacionado a consentimiento por Flow como estrategia principal queda deprecado por la decisión session-first del 2026-03-01.
  - Todo lo relacionado a onboarding template-first en inicio de sesión queda deprecado por costo/operación.
  - Se conserva en este registro solo para trazabilidad técnica.
- 2026-02-27:
  - [Histórico/deprecado] Plan reemplazado para enfoque sin Flows.
  - [Histórico/deprecado] Se define arquitectura de botones + solicitud de ubicación.
  - Se formaliza breakpoint antes de búsqueda asíncrona.
  - Se agregan invariantes obligatorios y modelo de datos definitivo (`customers` + `customer_service_requests`).
  - Se agrega criterio obligatorio: resolver ciudad cuando llegue solo `lat/lng` y evitar re-prompt de ciudad.
  - Se agrega gate de trazabilidad outbound para confirmar ausencia de `reply context` forzado por backend.
  - Se incorpora subplan operativo Fase 3A para activación runtime de geocoding.
  - Se exige evidencia de logs `geocode_*` y verificación outbound `has_context=false`.
  - Se condiciona cierre de Fase 3 a prueba real `lat/lng only` en teléfono.
  - Cierre operativo validado con prueba real (~3:37 PM local): `lat/lng` resuelto a ciudad (`Cuenca`) sin pedir texto.
  - Se cierra tema de reply visual como comportamiento del cliente WhatsApp Web (no del payload backend).
  - [Histórico/deprecado] Se agrega e implementa subplan Fase 2A: consentimiento interactivo con botones (`consent_accept|consent_decline`) y enlace `Read more`.
  - [Histórico/deprecado] Se evoluciona UX de consentimiento a 2 vistas: resumen (`Detalles`) y detalle (`Volver`) con IDs `consent_details|consent_back`.
  - Se confirma aprobación de plantilla Meta `tinkubot_politica_privacidad_v1` para apertura fuera de ventana de 24h.
- 2026-02-28:
  - Se corrige bypass de Fase 4 en `enrutador`: sin estado inicial + ciudad ya no puede saltar a búsqueda directa.
  - Se obliga transición a `confirm_service` antes de cualquier búsqueda.
  - Se agrega prueba de regresión `test_estado_vacio_con_ciudad_pasa_por_confirm_service_y_no_busca_directo`.
  - Se actualiza Gate Fase 4 a completado.
  - [Histórico/deprecado] Se simplifica consentimiento interactivo a 2 botones (`consent_accept|consent_decline`) con `ui.id=consent_prompt_v2`.
  - [Histórico/deprecado] Se elimina navegación `Detalles/Volver` tanto de UI como de backend (sin soporte legacy).
  - Se normaliza inbound interactivo para procesar `selected_option` y dejar `content` vacío en `interactive_*`.
- 2026-03-01:
  - Se define `session_first_v1` como estrategia principal de onboarding inicial.
  - Se implementa onboarding en un único mensaje `ui.type=buttons` con `header_type=image` y botón `continue_onboarding`.
  - Se habilita soporte outbound de header image en botones interactivos en `wa-gateway`.
  - Se mantiene `interactive_flow_reply` únicamente por compatibilidad temporal.
  - Se depreca Flow-first y template-first para onboarding inicial.
