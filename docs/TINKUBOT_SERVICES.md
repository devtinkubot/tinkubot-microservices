# TinkuBot Services

Guia unificada de servicios, puertos y validaciones para el equipo de desarrollo.

## Servicios Python

| Servicio | Puerto | Descripcion |
|----------|--------|-------------|
| **ai-search** | 8000 | Busqueda avanzada con tokenizacion, cache y estrategias hibridas |
| **ai-clientes** | 8001 | Procesamiento de mensajes de clientes con OpenAI |
| **ai-proveedores** | 8002 | Busqueda geolocalizada de proveedores con PostGIS |
| **av-proveedores** | 8005 | Verificacion de disponibilidad de proveedores |

Ejecucion (Docker):

```bash
docker compose up -d ai-search ai-clientes ai-proveedores av-proveedores
```

Health checks:

```bash
curl http://localhost:8000/api/v1/health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8005/health
```

## Servicios Node.js

| Servicio | Puerto | Descripcion |
|----------|--------|-------------|
| **wa-clientes** | 5001 | Bot de WhatsApp para clientes |
| **wa-proveedores** | 5002 | Bot de WhatsApp para proveedores |
| **frontend** | 5000 | UI y panel administrativo |

Ejecucion (Docker):

```bash
docker compose up -d wa-clientes wa-proveedores frontend
```

## Servicios Docker

Validacion de Dockerfiles y docker-compose:

```bash
python validate_docker.py
```

Recomendaciones:
- Imagen base con version fija (tag o digest)
- Healthcheck en cada servicio
- Limites de recursos y rotacion de logs
- Usuario no root en Dockerfiles

## Validacion de Calidad (Codigo)

Validacion unificada para Python y Node.js:

```bash
python validate_quality_code.py
```

Opciones utiles:

```bash
python validate_quality_code.py --stack python
python validate_quality_code.py --stack node
python validate_quality_code.py --service wa-clientes
python validate_quality_code.py --node-install
python validate_quality_code.py --node-audit
```

## Variables de Entorno Clave

Python (comunes):
- `OPENAI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_BACKEND_API_KEY`
- `SUPABASE_SERVICE_KEY`
- `REDIS_URL`

Node.js (WhatsApp):
- `SUPABASE_URL`
- `SUPABASE_BACKEND_API_KEY`
- `SUPABASE_BUCKET_NAME`
- `CLIENTES_INSTANCE_ID` / `PROVEEDORES_INSTANCE_ID`
- `CLIENTES_WHATSAPP_PORT` / `PROVEEDORES_WHATSAPP_PORT`

Infraestructura:
- `MQTT_BROKER_URL` (si aplica)
- `MOSQUITTO_PORT` (si aplica)

## Dependencias Entre Servicios

- `wa-clientes` -> `ai-clientes` (HTTP)
- `wa-proveedores` -> `ai-proveedores` (HTTP)
- `ai-search` <-> `ai-clientes` (HTTP interno)
- `av-proveedores` <-> `mosquitto` (MQTT)
- Servicios Python -> `Redis` y `Supabase`

## Despliegue y Rollback (Docker Compose)

Despliegue:

```bash
docker compose pull
docker compose up -d --build
docker compose ps
```

Rollback (ultimo estado estable):

```bash
docker compose up -d --build --force-recreate
```

## Troubleshooting Rapido

- **WA no responde**: revisar `docker logs tinkubot-wa-clientes` y validar QR/sesion.
- **Errores de salud**: verificar healthcheck del servicio y puertos.
- **AI no responde**: revisar `docker logs` y variables de entorno.
- **MQTT sin mensajes**: validar `mosquitto` en `docker compose ps`.

## Puertos Clave

- **MQTT**: 1883 (mosquitto)
- **Frontend**: 5000
- **WhatsApp clientes**: 5001
- **WhatsApp proveedores**: 5002
- **AI search**: 8000
- **AI clientes**: 8001
- **AI proveedores**: 8002
- **AV proveedores**: 8005
