# TinkuBot Python Services

Servicios de IA de TinkuBot implementados en Python con FastAPI, Redis y Supabase.

## Servicios Implementados

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| **ai-search** | 8000 | Búsqueda avanzada con tokenización, cache y estrategias híbridas |
| **ai-clientes** | 8001 | Procesamiento de mensajes de clientes con OpenAI |
| **ai-proveedores** | 8002 | Búsqueda geolocalizada de proveedores con PostGIS |
| **av-proveedores** | 8005 | Verificación de disponibilidad de proveedores |

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                      TINKUBOT PYTHON SERVICES                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │  ai-search   │      │ ai-clientes  │      │ai-proveedores │  │
│  │   Port 8000  │      │  Port 8001   │      │  Port 8002   │  │
│  │              │      │              │      │              │  │
│  │ • Tokenizac. │      │ • OpenAI     │      │ • PostGIS    │  │
│  │ • Cache      │◀────▶│ • Sesiones   │◀────▶│ • Geolocal.  │  │
│  │ • Embeddings │      │ • Flujos     │      │ • Matching   │  │
│  └──────────────┘      └──────┬───────┘      └──────────────┘  │
│                                │                                 │
│                        ┌───────┴────────┐                         │
│                        │    Redis      │                         │
│                        │   (Upstash)    │                         │
│                        └───────┬────────┘                         │
│                                │                                 │
│  ┌──────────────┐      ┌───────┴────────┐      ┌──────────────┐  │
│  │av-proveedores│      │   Supabase    │      │   Mosquitto  │  │
│  │  Port 8005   │      │  PostgreSQL   │      │    MQTT      │  │
│  │              │      │   + PostGIS   │      │   Port 1883  │  │
│  │ • Disp.      │◀────▶│              │      │              │  │
│  └──────────────┘      └───────────────┘      └──────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Comunicación con Servicios Node.js

Los servicios Python se comunican con los servicios de WhatsApp (Node.js) a través de HTTP:

- **wa-clientes** (Puerto 5001) → **ai-clientes** (Puerto 8001)
- **wa-proveedores** (Puerto 5002) → **ai-proveedores** (Puerto 8002)

## Tecnologías Utilizadas

- **FastAPI**: Framework web moderno y rápido
- **AsyncIO**: Programación asíncrona para alto rendimiento
- **Redis (Upstash)**: Cache y Pub/Sub
- **Supabase**: Persistencia (PostgreSQL + PostGIS)
- **OpenAI**: Procesamiento de lenguaje natural
- **httpx**: Cliente HTTP asíncrono
- **paho-mqtt**: Cliente MQTT para comunicación con av-proveedores

## Instalación y Configuración

### Requisitos Previos

- Python 3.11+
- Docker y Docker Compose
- Cuenta de Supabase con extensión PostGIS
- Cuenta de Upstash Redis
- API Key de OpenAI

### Configuración Inicial

1. **Configurar variables de entorno**
   ```bash
   cp .env.example .env
   # Editar .env con tus configuraciones
   ```

2. **Iniciar servicios con Docker**
   ```bash
   docker compose up -d ai-search ai-clientes ai-proveedores av-proveedores
   ```

### Variables de Entorno Requeridas

```bash
# OpenAI
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_MAX_TOKENS=150
OPENAI_TEMPERATURE=0.7

# Supabase/PostgreSQL
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_BACKEND_API_KEY=your-backend-key
SUPABASE_SERVICE_KEY=your-service-key
DATABASE_URL=postgresql://user:password@host:5432/dbname

# Redis Upstash
REDIS_URL=rediss://:token@host

# Puertos de servicios Python
AI_SEARCH_PORT=8000
CLIENTES_SERVER_PORT=8001
PROVEEDORES_SERVER_PORT=8002
AV_PROVEEDORES_PUERTO=8005
```

## Health Checks

```bash
# ai-search
curl http://localhost:8000/api/v1/health

# ai-clientes
curl http://localhost:8001/health

# ai-proveedores
curl http://localhost:8002/health

# av-proveedores
curl http://localhost:8005/health
```

## APIs de los Servicios

### AI Search (Puerto 8000)

**Endpoints principales:**

- `GET /api/v1/health` - Health check
- `GET /api/v1/stats` - Estadísticas del servicio
- `POST /api/v1/search` - Búsqueda de proveedores

**Ejemplo de uso:**

```bash
curl -X POST "http://localhost:8000/api/v1/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "plomero en Quito",
    "limit": 10
  }'
```

### AI Clientes (Puerto 8001)

**Endpoints principales:**

- `GET /health` - Health check
- `GET /` - Información del servicio
- `POST /process-message` - Procesar mensaje de cliente
- `POST /handle-whatsapp-message` - Manejar mensaje de WhatsApp

**Ejemplo de uso:**

```bash
curl -X POST "http://localhost:8001/process-message" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Necesito un plomero en Quito",
    "phone": "+593998823053"
  }'
```

### AI Proveedores (Puerto 8002)

**Endpoints principales:**

- `GET /health` - Health check
- `GET /` - Información del servicio
- `POST /register` - Registrar nuevo proveedor
- `POST /search` - Búsqueda geolocalizada de proveedores
- `GET /providers/stats` - Estadísticas de proveedores

**Ejemplo de uso:**

```bash
curl -X POST "http://localhost:8002/search" \
  -H "Content-Type: application/json" \
  -d '{
    "profession": "plomero",
    "location": "Quito",
    "radius": 10.0
  }'
```

### AV Proveedores (Puerto 8005)

**Endpoints principales:**

- `GET /health` - Health check
- `POST /check-availability` - Verificar disponibilidad de proveedores

## Desarrollo Local

### Ejecutar sin Docker

Si prefieres desarrollar localmente sin Docker:

```bash
# ai-search
cd python-services/ai-search
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# ai-clientes
cd python-services/ai-clientes
pip install -r requirements.txt
python main.py

# ai-proveedores
cd python-services/ai-proveedores
pip install -r requirements.txt
python main.py

# av-proveedores
cd python-services/av-proveedores
pip install -r requirements.txt
python main.py
```

## Validación de Calidad

Antes de hacer commit, ejecuta la validación:

```bash
cd python-services
python validate_quality.py
```

La validación incluye:
- **Black**: Formato de código
- **isort**: Ordenamiento de importaciones
- **Flake8**: Linting
- **MyPy**: Verificación de tipos
- **Bandit**: Análisis de seguridad

## Estructura de Directorios

```
python-services/
├── ai-clientes/           # Bot de clientes
│   ├── main.py           # Punto de entrada
│   ├── flows/            # Flujos de conversación
│   ├── templates/        # Prompts de OpenAI
│   └── requirements.txt
├── ai-proveedores/       # Bot de proveedores
│   ├── main.py           # Punto de entrada
│   ├── flows/            # Flujos de registro
│   ├── templates/        # Prompts de OpenAI
│   └── requirements.txt
├── ai-search/            # Servicio de búsqueda
│   ├── app/
│   │   ├── main.py       # Punto de entrada
│   │   └── api/          # Endpoints FastAPI
│   ├── services/         # Lógica de negocio
│   └── requirements.txt
├── av-proveedores/       # Verificación disponibilidad
│   ├── main.py
│   └── requirements.txt
├── shared-lib/           # Biblioteca compartida
│   ├── config.py         # Configuración centralizada
│   ├── redis_client.py   # Cliente Redis
│   └── session_timeout.py # Gestión de sesiones
└── validate_quality.py   # Script de validación
```

## Logs y Monitoreo

### Ver logs en Docker

```bash
# Todos los servicios Python
docker compose logs -f ai-search ai-clientes ai-proveedores av-proveedores

# Servicio específico
docker compose logs -f ai-clientes
```

### Niveles de Logging

Los servicios usan `structlog` para logging estructurado:

- **INFO**: Operaciones normales
- **WARNING**: Situaciones inusuales
- **ERROR**: Errores que necesitan atención
- **DEBUG**: Información detallada para desarrollo

## Troubleshooting

### Problemas Comunes

**1. Servicios no se conectan a Redis**
- Verificar `REDIS_URL` en `.env`
- Confirmar que Redis está accesible

**2. Error de conexión a Supabase**
- Verificar `SUPABASE_URL` y claves API
- Confirmar que las tablas existen en Supabase

**3. Timeouts en OpenAI**
- Verificar `OPENAI_API_KEY` es válida
- Revisar cuota de uso de OpenAI

## Contribución

1. Fork del repositorio
2. Crear rama: `git checkout -b feature/nueva-funcionalidad`
3. Implementar cambios
4. Ejecutar `python validate_quality.py`
5. Commit y push
6. Abrir Pull Request
