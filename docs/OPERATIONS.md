# TinkuBot Operación (Clientes/Proveedores)

Este documento resume variables de entorno clave, comandos de despliegue y verificación para los servicios de Atención al Cliente (Node + Python) y Proveedores.

## Variables de entorno clave

### AI Service Clientes (python-services/ai-service-clientes)
- **FEEDBACK_DELAY_SECONDS**: segundos para pedir calificación diferida (ej. 300 en pruebas, 14400 en prod).
- **TASK_POLL_INTERVAL_SECONDS**: intervalo de polling de tareas (por defecto 60).
- **FLOW_TTL_SECONDS**: TTL del flujo conversacional en Redis (por defecto 3600).
- **PROVEEDORES_AI_SERVICE_URL**: URL del servicio de Proveedores (por defecto http://ai-service-proveedores:5007).
- **WHATSAPP_CLIENTES_URL**: URL interna del WhatsApp Clientes (por defecto http://whatsapp-service-clientes:8005).
- **SUPABASE_URL / SUPABASE_BACKEND_API_KEY**: credenciales de Supabase para tabla `customers` y `consents`.
- **REDIS_URL**: URL de Redis (Upstash).
- **OPENAI_API_KEY**: API key de OpenAI para procesamiento de lenguaje natural.

### AI Service Proveedores (python-services/ai-service-proveedores)
- **SUPABASE_URL / SUPABASE_BACKEND_API_KEY**: credenciales para gestión de proveedores.
- **DATABASE_URL**: PostgreSQL directo para búsqueda geolocalizada.
- **OPENAI_API_KEY**: opcional para respuestas generales.
- **REDIS_URL**: URL de Redis (si aplica).

### WhatsApp Clientes (nodejs-services/whatsapp-service-clientes)
- **AI_SERVICE_CLIENTES_URL**: URL del AI Clientes (por defecto http://ai-service-clientes:5003).
- **SUPABASE_URL / SUPABASE_BACKEND_API_KEY / SUPABASE_BUCKET_NAME**: sesión remota con RemoteAuth.
- **WHATSAPP_PORT**: puerto expuesto (por defecto 8005).
- **INSTANCE_ID**: identificador único (clientes).

### WhatsApp Proveedores (nodejs-services/whatsapp-service-proveedores)
- **PROVEEDORES_AI_SERVICE_URL**: URL del AI Proveedores (por defecto http://ai-service-proveedores:5007).
- **SUPABASE_URL / SUPABASE_BACKEND_API_KEY / SUPABASE_BUCKET_NAME**: sesión remota.
- **WHATSAPP_PORT**: puerto expuesto (por defecto 8006).
- **INSTANCE_ID**: identificador único (proveedores).

## Despliegue rápido

- Habilitar BuildKit y builds en paralelo:
```
export DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1
```
- Construir y levantar servicios principales (clientes):
```
docker compose build --parallel ai-service-clientes whatsapp-service-clientes
docker compose up -d ai-service-clientes whatsapp-service-clientes
```
- Limpiar caché en caso de builds lentos:
```
docker builder prune -f
```

## Endpoints útiles

### WhatsApp Clientes (8005)
- **Estado simple**: `GET /status`
- **Health**: `GET /health`
- **QR Code**: `GET /qr` (obtener código QR para escanear)
- **Envío de texto (scheduler)**: `POST /send` body `{ to, message }`

### AI Service Clientes (5003)
- **Health**: `GET /health`
- **Manejo de WhatsApp**: `POST /handle-whatsapp-message` (uso interno por WhatsApp Service)
- **Procesamiento general**: `POST /process-message`
- **Sesiones (compat)**:
  - `POST /sessions`
  - `GET /sessions/{phone}`
  - `DELETE /sessions/{phone}`
  - `GET /sessions/stats`

### AI Service Proveedores (5007)
- **Health**: `GET /health`
- **Búsqueda**: `POST /search-providers`
- **Registro**: `POST /register-provider`
- **Estadísticas**: `GET /providers/stats`

## Operación diaria

- Ver logs en vivo:
```
docker compose logs -f whatsapp-service-clientes
```
- Reinicio focalizado (clientes):
```
docker compose up -d ai-service-clientes whatsapp-service-clientes
```
- Cambiar tiempo de feedback diferido:
  - Establecer `FEEDBACK_DELAY_SECONDS` (p. ej. 300 pruebas, 14400 prod) en el entorno del contenedor de AI Clientes y reiniciar ese servicio.

## Flujos y atajos

### Flujo de Consentimiento (Implementado)
1. **Detección**: Nuevo cliente o cliente sin `has_consent = true`
2. **Solicitud**: Bot envía mensaje con información sobre qué datos se compartirán, seguido del recordatorio `*Responde con el número de tu opción:*` y las opciones numeradas:
   - `1 Acepto`
   - `2 No acepto`
3. **Registro**:
   - Si acepta: Actualiza `customers.has_consent = true` y crea registro en `consents`
   - Si rechaza: Registra rechazo en `consents` y ofrece ayuda directa
4. **Continuación**: Solo clientes con consentimiento pueden acceder al flujo de búsqueda

### Flujo de Búsqueda de Servicios
- **Reset por chat**: enviar `reset` limpia la ciudad guardada, reinicia el flujo y responde "¿Qué servicio necesitas hoy?"
- **Tipos de mensaje aceptados**: `chat`, `location`, `live_location`. Mensajes internos (e.g., `notification_template`) se ignoran.
- **Flujo de petición**: Solo si tiene consentimiento → se solicita servicio, luego ciudad (si es la primera vez o tras un cambio) y se dispara la búsqueda.
- **Sin proveedores**: Se muestra `-- No tenemos aún proveedores --` y el menú incluye `0 Buscar en otra ciudad`, `1 Buscar otro servicio`, `2 No, por ahora está bien`.
- **Múltiples proveedores**: Si el cliente rechaza la primera opción, se ofrece `0 Elegir otro proveedor` para volver a listar al resto.
- **Conexión con proveedor**: Mensaje minimalista + link `wa.me` para abrir chat.
- **Feedback diferido**: Se agenda vía `task_queue` y se envía en `FEEDBACK_DELAY_SECONDS`.

### Estados del Cliente
- **Nuevo (has_consent = null)**: Muestra solicitud de consentimiento
- **Sin consentimiento (has_consent = false)**: Bloqueado, muestra mensaje de ayuda directa
- **Con consentimiento (has_consent = true)**: Flujo normal de búsqueda activado

### Comandos Útiles
- **"hola"**: Inicia conversación (verifica consentimiento primero)
- **"reset"**: Limpia ciudad guardada, restablece `has_consent = false` y reinicia flujo
- **Responder "1" o "2"**: Selecciona opciones de botones
- **Opción "0"**: Cambiar ciudad o elegir otro proveedor (dependiendo del contexto)

## Troubleshooting

- ENOTFOUND ai-service-clientes: asegúrate que el contenedor `ai-service-clientes` esté “healthy” y en la misma red de Docker.
- Sólo veo notificaciones y no “chat”: abre manualmente el chat con el número del bot y envía texto simple (“hola”). Verifica que el log muestre `tipo: chat`.
- Build lento (Chrome): la capa `apt-get install chromium` puede tardar la primera vez; las siguientes builds usan caché. Usa BuildKit y `--parallel`.
