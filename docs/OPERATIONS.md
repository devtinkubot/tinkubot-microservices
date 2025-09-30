# TinkuBot Operación (Clientes/Proveedores)

Este documento resume variables de entorno clave, comandos de despliegue y verificación para los servicios de Atención al Cliente (Node + Python) y Proveedores.

## Variables de entorno clave

### AI Service Clientes (python-services/ai-service-clientes)
- FEEDBACK_DELAY_SECONDS: segundos para pedir calificación diferida (ej. 300 en pruebas, 14400 en prod).
- TASK_POLL_INTERVAL_SECONDS: intervalo de polling de tareas (por defecto 60).
- FLOW_TTL_SECONDS: TTL del flujo conversacional en Redis (por defecto 3600).
- PROVEEDORES_AI_SERVICE_URL: URL del servicio de Proveedores (por defecto http://ai-service-proveedores:5002).
- WHATSAPP_CLIENTES_URL: URL interna del WhatsApp Clientes (por defecto http://whatsapp-service-clientes:7001).
- SUPABASE_URL / SUPABASE_BACKEND_API_KEY: credenciales de Supabase.
- REDIS_URL: URL de Redis (Upstash).

### AI Service Proveedores (python-services/ai-service-proveedores)
- SUPABASE_URL / SUPABASE_BACKEND_API_KEY: credenciales.
- OPENAI_API_KEY: opcional para respuestas generales.
- REDIS_URL: URL de Redis (si aplica).

### WhatsApp Clientes (nodejs-services/whatsapp-service-clientes)
- AI_SERVICE_CLIENTES_URL: URL del AI Clientes (por defecto http://ai-service-clientes:5001).
- SUPABASE_URL / SUPABASE_BACKEND_API_KEY / SUPABASE_BUCKET_NAME: sesión remota con RemoteAuth.
- WHATSAPP_PORT: puerto expuesto (por defecto 7001).

### WhatsApp Proveedores (nodejs-services/whatsapp-service-proveedores)
- PROVEEDORES_AI_SERVICE_URL: URL del AI Proveedores (por defecto http://ai-service-proveedores:5002).
- SUPABASE_URL / SUPABASE_BACKEND_API_KEY / SUPABASE_BUCKET_NAME.
- WHATSAPP_PORT: puerto expuesto (por defecto 7002).

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

### WhatsApp Clientes (7001)
- Estado simple: `GET /status`
- Health: `GET /health`
- Envío de texto (scheduler): `POST /send` body `{ to, message }`

### AI Service Clientes (5001)
- Health: `GET /health`
- Manejo de WhatsApp: `POST /handle-whatsapp-message` (uso interno por WhatsApp Service)
- Sesiones (compat):
  - `POST /sessions`
  - `GET /sessions/{phone}`
  - `DELETE /sessions/{phone}`

### AI Service Proveedores (5002)
- Health: `GET /health`
- Búsqueda: `POST /search-providers`
- Registro: `POST /register-provider`

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

- Reset por chat: enviar `reset` reinicia el flujo y responde “¿Qué servicio necesitas hoy?”
- Tipos de mensaje aceptados en WhatsApp: `chat`, `location`, `live_location`. Mensajes internos (e.g., `notification_template`) se ignoran.
- “Toda la ciudad (3)”: ejecuta búsqueda inmediata sin pedir ubicación.
- Conexión con proveedor: mensaje minimalista + link `wa.me` para abrir chat.
- Feedback diferido: se agenda vía `task_queue` y se envía en `FEEDBACK_DELAY_SECONDS`.

## Troubleshooting

- ENOTFOUND ai-service-clientes: asegúrate que el contenedor `ai-service-clientes` esté “healthy” y en la misma red de Docker.
- Sólo veo notificaciones y no “chat”: abre manualmente el chat con el número del bot y envía texto simple (“hola”). Verifica que el log muestre `tipo: chat`.
- Build lento (Chrome): la capa `apt-get install chromium` puede tardar la primera vez; las siguientes builds usan caché. Usa BuildKit y `--parallel`.

