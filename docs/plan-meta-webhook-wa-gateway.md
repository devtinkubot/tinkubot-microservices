# Plan de Integracion Meta Webhook en `wa-gateway`

## Resumen
Se implementara la integracion de WhatsApp Cloud API de Meta en el microservicio existente `go-services/wa-gateway`, manteniendo un solo borde de mensajeria para el proyecto.

Decisiones base:
- Callback URL: `https://webhook.tinku.bot/meta/webhook`
- Estrategia inicial: `1 app + 1 URL`
- Seguridad inicial: HTTPS + `verify_token` + validacion de `X-Hub-Signature-256`
- mTLS: no en fase inicial
- Feature flag: habilitado para rollout controlado

## Objetivos
1. Recibir y validar webhooks de Meta desde un endpoint publico y seguro.
2. Mantener compatibilidad con los endpoints actuales de `wa-gateway`.
3. Permitir activacion gradual con feature flags.
4. Tener capacidad de rollback inmediato sin cambios de arquitectura.

## Contexto del proyecto
- `wa-gateway` ya es el borde de WhatsApp y enruta eventos hacia `ai-clientes`/`ai-proveedores`.
- Frontend/admin consume `wa-gateway` para estado de cuentas, login/QR y envio.
- `manager.tinku.bot` se mantiene para frontend/admin; webhook externo debe ir en subdominio tecnico separado.

## Decision de arquitectura
### Opcion seleccionada
Extender `wa-gateway` con un provider/adapter Meta interno.

### Opcion descartada por ahora
Crear microservicio separado `wa-meta`.

Razon:
- Menor complejidad operativa.
- Menor duplicacion de rutas y observabilidad.
- Reuso del contrato actual del gateway.

## Feature Flags
### Flags propuestos
- `WA_META_WEBHOOK_ENABLED=false`
- `WA_META_ENABLED_ACCOUNTS=bot-clientes,bot-proveedores` (opcional, para control fino)

### Comportamiento esperado
- `GET /meta/webhook`:
  - Flag OFF: responder `404` (recomendado) o `503`.
  - Flag ON: procesar verificacion Meta.
- `POST /meta/webhook`:
  - Flag OFF: rechazar rapido.
  - Flag ON: validar firma y procesar evento.

## API y contratos
### Endpoint de verificacion
- `GET /meta/webhook`
- Query params esperados:
  - `hub.mode`
  - `hub.verify_token`
  - `hub.challenge`
- Respuesta:
  - `200` + cuerpo `hub.challenge` si token coincide.
  - `403` si token invalido.

### Endpoint de eventos
- `POST /meta/webhook`
- Header de seguridad:
  - `X-Hub-Signature-256`
- Validacion:
  - HMAC SHA-256 del body con `META_APP_SECRET`
- Respuesta:
  - `200` cuando se acepta el evento.
  - `401/403` en firma invalida.

## Configuracion y secretos
Variables de entorno nuevas:
- `META_WEBHOOK_VERIFY_TOKEN`
- `META_APP_SECRET`
- `META_WEBHOOK_PATH=/meta/webhook` (opcional, no usado en fase actual)
- `META_PHONE_NUMBER_ID_CLIENTES`
- `WA_META_WEBHOOK_ENABLED=false`
- `WA_META_ENABLED_ACCOUNTS=` (opcional)

No versionar tokens/secrets en repo.
Nota de seguridad: si algun access token se comparte fuera de un canal seguro, rotarlo.

## DNS y Tunnel
### Dominio recomendado
- `webhook.tinku.bot`

### Callback final en Meta
- `https://webhook.tinku.bot/meta/webhook`

### Cloudflare Tunnel
- Exponer `webhook.tinku.bot` hacia `wa-gateway:7000`.
- Asegurar que el path `/meta/webhook` llegue a `wa-gateway`.

## Seguridad
1. Verificacion por `verify_token` en `GET`.
2. Verificacion de firma `X-Hub-Signature-256` en `POST`.
3. Logging sin exponer payload sensible completo.
4. Rate limiting basico por IP/path (si aplica al borde).

## Observabilidad
Metricas sugeridas:
- conteo de requests `GET/POST /meta/webhook`
- porcentaje de firmas invalidas
- latencia p50/p95 del webhook
- errores por tipo de validacion

Logs sugeridos:
- request_id
- resultado de verificacion (token/firma)
- tipo de evento Meta
- account_id derivado

## Plan de implementacion
1. Agregar rutas `GET/POST /meta/webhook` en `wa-gateway`.
2. Implementar verificacion de token y challenge.
3. Implementar validacion HMAC de firma.
4. Enrutar payload validado al flujo interno correspondiente.
5. Incorporar feature flags ON/OFF.
6. Ajustar `docker-compose` y `.env.example`.
7. Agregar tests unitarios y de integracion.
8. Desplegar con flag OFF.
9. Validar handshake desde Meta.
10. Activar flag en entorno objetivo.

## Estado actual (2026-02-25)
Implementacion completada en `wa-gateway`:
- Rutas activas: `GET /meta/webhook` y `POST /meta/webhook`.
- Seguridad activa: `verify_token` + firma `X-Hub-Signature-256` (HMAC SHA-256).
- Feature flag en uso: `WA_META_WEBHOOK_ENABLED=true`.
- Mapeo fase 1: `META_PHONE_NUMBER_ID_CLIENTES -> bot-clientes`.

Tunnel Cloudflare operativo:
- `manager.tinku.bot -> http://localhost:5000`
- `webhook.tinku.bot -> http://localhost:7000`

Limitacion conocida:
- El test number de Meta no se comporta como numero WhatsApp productivo para chat libre.
- El endpoint `request_code/verify_code` aplica a numero propio verificable, no al flujo de uso normal del test number.

## Evidencia de validacion
1. Handshake desde Meta exitoso:
- `GET /meta/webhook` con token correcto retorna `200`.

2. Seguridad:
- `GET /meta/webhook` con token incorrecto retorna `403`.
- `POST /meta/webhook` con firma invalida retorna `401`.
- `POST /meta/webhook` con firma valida retorna `200`.

3. Reenvio interno:
- `wa-gateway` registro `Message sent successfully` hacia `ai-clientes` con `account=bot-clientes`.
- `ai-clientes` registro `Set flow ... AWAITING_CONSENT` para `15551940937@s.whatsapp.net`.

## Variables efectivas de fase 1
- `WA_META_WEBHOOK_ENABLED=true`
- `WA_META_ENABLED_ACCOUNTS=bot-clientes`
- `META_WEBHOOK_VERIFY_TOKEN=<definido en .env>`
- `META_APP_SECRET=<definido en .env>`
- `META_PHONE_NUMBER_ID_CLIENTES=885731614631934`

## Pendiente para manana (migracion numero real)
1. Obtener `Phone Number ID` del numero real (no WABA ID).
2. Actualizar `.env`:
- `META_PHONE_NUMBER_ID_CLIENTES=<nuevo_phone_number_id>`
3. Recreate:
- `docker compose up -d --force-recreate wa-gateway`
4. Revalidar:
- Handshake `GET /meta/webhook` desde Meta.
- `POST /meta/webhook` firmado correctamente.
- Flujo real de mensaje entrante end-to-end.
5. Confirmar en Meta Webhooks que el campo `messages` este suscrito.

Rollback rapido:
1. `WA_META_WEBHOOK_ENABLED=false`
2. `docker compose up -d --force-recreate wa-gateway`
3. Revisar logs antes de reactivar.

## Pruebas y criterios de aceptacion
1. Handshake exitoso:
- Meta valida callback y token con `GET`.

2. Evento valido:
- `POST` firmado correctamente retorna `200`.

3. Evento invalido:
- firma invalida retorna `401/403`.

4. Flag OFF:
- endpoint deshabilitado segun politica definida.

5. No regresion:
- `/accounts`, `/send`, `/events/stream` siguen operativos.

## Rollout y rollback
### Rollout
1. Deploy con flag OFF.
2. Configurar callback en Meta.
3. Probar handshake.
4. Activar flag ON.
5. Monitorear errores/latencia.

### Rollback
1. Poner `WA_META_WEBHOOK_ENABLED=false`.
2. Mantener `wa-gateway` activo para flujos actuales.
3. Revisar logs y ajustar antes de reactivar.

## Riesgos y mitigaciones
- Riesgo: eventos no autenticados.
  - Mitigacion: validar firma obligatoriamente.
- Riesgo: mezcla de responsabilidades con frontend.
  - Mitigacion: dominio separado `webhook.tinku.bot`.
- Riesgo: ruido operativo con una sola app/URL.
  - Mitigacion: logging estructurado + flags por cuenta.

## Supuestos
- Se mantiene una sola app de Meta en la fase inicial.
- `manager.tinku.bot` no se usa para callback de Meta.
- El equipo prioriza time-to-market con seguridad base robusta.
