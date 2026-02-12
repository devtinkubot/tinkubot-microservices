# TinkuBot Microservices

Sistema de microservicios de IA para TinkuBot con Python (FastAPI), Node.js, Redis Pub/Sub y Supabase/PostGIS.

## Estructura del Proyecto

```
tinkubot-microservices/
├── python-services/          # Servicios de IA en Python
│   ├── ai-clientes/          # Procesamiento de mensajes de clientes
│   ├── ai-proveedores/       # Gestión de proveedores
│   └── ai-search/            # Búsqueda semántica con embeddings
├── node-services/            # Servicios en Node.js
│   └── whatsapp-gateway/     # Gateway de WhatsApp
├── docs/                     # Documentación SQL y migraciones
├── scripts/                  # Scripts de utilidad
└── docker-compose.yml        # Orquestación de contenedores
```

## Servicios Implementados

1. **AI Search** (Puerto 8000)
   - Búsqueda semántica de proveedores con embeddings
   - Búsqueda por tokens y full-text search
   - Cache ultrarrápido con Redis
   - Matching basado en similitud de servicios

2. **AI Clientes** (Puerto 8001)
   - Procesamiento de mensajes de clientes con OpenAI
   - Entendimiento de necesidades y extracción de información
   - Coordinación con servicio de búsqueda
   - Gestión de sesiones integrada
   - Sistema de leads y retroalimentación

3. **AI Proveedores** (Puerto 8002)
   - Registro de proveedores con embeddings por servicio
   - Búsqueda geolocalizada con PostGIS
   - Gestión de disponibilidad y perfiles
   - Hasta 7 servicios por proveedor con embeddings individuales

4. **WhatsApp Gateway** (Node.js)
   - Integración con WhatsApp Business API
   - Webhook handling
   - Envío de mensajes multimedia

## Tecnologías

- **FastAPI**: Framework web asíncrono para Python
- **Redis (Upstash)**: Cache y almacenamiento de sesiones
- **Supabase/PostgreSQL**: Persistencia con extensión PostGIS
- **OpenAI**: Procesamiento de lenguaje natural y embeddings
- **pgvector**: Búsqueda semántica con vectores

## Instalación y Configuración

### Requisitos Previos

- Python 3.11+
- Node.js 18+
- PostgreSQL con extensiones PostGIS y pgvector
- Cuenta de Upstash Redis
- API Key de OpenAI

### Configuración Inicial

1. **Clonar y configurar variables de entorno**
   ```bash
   cp .env.example .env
   # Editar .env con tus configuraciones
   ```

### Variables de Entorno Requeridas

```bash
# OpenAI
OPENAI_API_KEY=tu-api-key-aqui

# Supabase/PostgreSQL
SUPABASE_URL=tu-supabase-url
SUPABASE_SERVICE_KEY=tu-service-key
DATABASE_URL=postgresql://usuario:password@host:puerto/basedatos

# Redis Upstash (Pub/Sub y Cache)
REDIS_URL=rediss://:password@host:puerto

# Embeddings (búsqueda semántica)
EMBEDDINGS_ENABLED=true
EMBEDDINGS_MODEL=text-embedding-3-small
EMBEDDINGS_CACHE_TTL=3600

# Puertos de servicios
CLIENTES_SERVICE_PORT=5001
PROVEEDORES_SERVICE_PORT=5002
SEARCH_SERVICE_PORT=5000
```

## Ejecución

### Método Recomendado: Docker Compose

```bash
# Iniciar todos los servicios
docker compose up -d

# Verificar estado
docker compose ps
```

### Desarrollo Local (sin Docker)

**AI Search**

```bash
cd python-services/ai-search
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 5000
```

**AI Clientes**

```bash
cd python-services/ai-clientes
pip install -r requirements.txt
python main.py
```

**AI Proveedores**

```bash
cd python-services/ai-proveedores
pip install -r requirements.txt
python main.py
```

**WhatsApp Gateway**

```bash
cd node-services/whatsapp-gateway
npm install
npm run dev
```

### Verificar Estado

```bash
# AI Search
curl http://localhost:5000/health

# AI Clientes
curl http://localhost:5001/health

# AI Proveedores
curl http://localhost:5002/health
```

## Validación de Calidad Local

Antes de subir cambios a GitHub, ejecutar la validación de calidad.

### Flujo de Trabajo

1. Hacer cambios en el código
2. Ejecutar validación de calidad
3. Si todo está OK: Hacer commit y push
4. Si hay errores: Corregir y repetir

### Ejecutar Validación

```bash
# Validar todos los servicios (recomendado)
python python-services/validate_quality.py

# Validar solo un servicio específico
python python-services/validate_quality.py --service ai-clientes

# Validar y corregir automáticamente (formato e importaciones)
python python-services/validate_quality.py --fix
```

### Herramientas de Validación

El script ejecuta automáticamente:

- **Black**: Formato automático de código
- **isort**: Ordenamiento de importaciones
- **Flake8**: Linting y estilo de código
- **MyPy**: Verificación de tipos estáticos
- **Bandit**: Análisis de seguridad

## API Documentation

### AI Search (Puerto 5000)

- `GET /health` - Health check
- `POST /search` - Búsqueda semántica de proveedores

```bash
curl -X POST "http://localhost:5000/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "necesito un plomero para emergencia",
    "location": {"lat": -0.1807, "lng": -78.4678},
    "radius_km": 10.0
  }'
```

### AI Clientes (Puerto 5001)

- `GET /health` - Health check
- `POST /process-message` - Procesar mensaje con IA
- `POST /handle-whatsapp-message` - Manejar mensaje de WhatsApp
- `POST /sessions` - Guardar mensaje en sesión
- `GET /sessions/{phone}` - Obtener historial de conversación
- `DELETE /sessions/{phone}` - Eliminar sesiones de usuario

```bash
curl -X POST "http://localhost:5001/process-message" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Necesito un plomero en Quito",
    "user_type": "cliente",
    "context": {"phone": "+593998823053"}
  }'
```

### AI Proveedores (Puerto 5002)

- `GET /health` - Health check
- `POST /register-provider` - Registrar nuevo proveedor
- `PUT /update-provider/{id}` - Actualizar proveedor
- `GET /provider/{id}` - Obtener proveedor
- `POST /provider/services` - Actualizar servicios del proveedor

## Comunicación entre Servicios

Los servicios se comunican a través de **Redis Pub/Sub** y **HTTP**:

### Flujo Principal

1. Cliente envía mensaje a WhatsApp
2. WhatsApp Gateway → AI Clientes (HTTP)
3. AI Clientes procesa y guarda sesión automáticamente
4. AI Clientes → AI Search (HTTP) para búsqueda semántica
5. AI Clientes responde al cliente vía WhatsApp Gateway

### Ventajas

- Sesiones automáticas sin llamadas adicionales
- Contexto integrado con historial de conversación
- Comunicación asíncrona eficiente

## Testing

```bash
# Ejecutar tests
cd python-services && pytest

# Tests con coverage
pytest --cov=. --cov-report=html

# Type checking
mypy .
```

## Base de Datos

### Tablas Principales

```sql
-- Proveedores
CREATE TABLE providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(20) NOT NULL UNIQUE,
    location_lat DECIMAL(10, 8),
    location_lng DECIMAL(11, 8),
    rating DECIMAL(3, 2) DEFAULT 0.0,
    available BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Servicios de proveedores (con embeddings individuales)
CREATE TABLE provider_services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID REFERENCES providers(id) ON DELETE CASCADE,
    service_name VARCHAR(255) NOT NULL,
    description TEXT,
    embedding vector(1536),
    is_primary BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Leads (solicitudes de clientes)
CREATE TABLE leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_phone VARCHAR(20) NOT NULL,
    provider_phone VARCHAR(20) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Retroalimentación
CREATE TABLE lead_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(id),
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Índices

- Geoespacial: `idx_providers_location` para búsquedas por ubicación
- HNSW: Índice vectorial para búsqueda semántica en `provider_services`
- Búsqueda full-text: Para búsquedas por texto en servicios

## Despliegue

### Docker

```bash
# Construir imágenes
docker compose build

# Iniciar servicios
docker compose up -d

# Ver logs
docker compose logs -f
```

### Producción

1. Configurar variables de entorno en el servidor
2. Usar un reverse proxy (nginx/traefik)
3. Configurar SSL/TLS
4. Monitorear con health checks

## Monitoreo

```bash
# Ver logs en tiempo real
docker compose logs -f

# Ver logs de un servicio específico
docker compose logs -f ai-clientes
```

Los servicios exponen health checks en `/health` para monitoreo.

## Contribución

1. Hacer fork del repositorio
2. Crear feature branch
3. Implementar cambios
4. Ejecutar validación de calidad: `python python-services/validate_quality.py`
5. Hacer pull request

## Licencia

Este proyecto está bajo la Licencia MIT.

## Soporte

Para problemas o preguntas, crear un issue en el repositorio.
