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

## Puertos Clave

- **MQTT**: 1883 (mosquitto)
- **Frontend**: 5000
- **WhatsApp clientes**: 5001
- **WhatsApp proveedores**: 5002
- **AI search**: 8000
- **AI clientes**: 8001
- **AI proveedores**: 8002
- **AV proveedores**: 8005
