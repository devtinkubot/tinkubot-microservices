# Search Service

Microservicio especializado en búsqueda ultra-rápida de proveedores para TinkuBot.

## 🚀 Características

- **Embeddings-only**: búsqueda semántica vectorial como única estrategia
- **Caché inteligente**: Redis para respuestas instantáneas
- **Normalización avanzada**: texto sin acentos, minúsculas, sin caracteres especiales

## 📋 Arquitectura

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   AI Clientes   │───▶│  Search Service  │───▶│  PostgreSQL     │
│                 │    │  (FastAPI)       │    │  + Índices      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                       ┌────────▼────────┐
                       │   Redis Cache   │
                       └─────────────────┘
                                │
                       ┌────────▼────────┐
                       │   OpenAI API    │
                       │  (obligatorio)  │
                       └─────────────────┘
```

## 🏃‍♂️ Inicio Rápido

### 1. Variables de Entorno

```bash
cp .env.example .env
# Editar .env con tus configuraciones
```

### 2. con Docker (a través del proyecto principal)

El servicio search-token se ejecuta como parte del docker-compose principal del proyecto:

```bash
# Desde la raíz del proyecto
docker compose up -d search-token
```

### 3. Local

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 📚 API Documentation

Una vez iniciado, visita:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🔍 Endpoints Principales

### Buscar Proveedores

```bash
POST /api/v1/search
Content-Type: application/json

{
  "query": "necesito médico en Quito urgente",
  "filters": {
    "min_rating": 4.0,
    "city": "Quito"
  },
  "limit": 10
}
```

### Sugerencias de Autocompletado

```bash
GET /api/v1/suggestions?q=médico&limit=5
```

### Analizar Consulta

```bash
GET /api/v1/analyze?q=necesito plomero en guayaquil
```

### Health Check

```bash
GET /api/v1/health
```

## 🎯 Estrategia de Búsqueda

### Embeddings (única estrategia)
- **Cómo funciona**: genera embedding de una consulta canónica y hace match vectorial en base de datos.
- **Consulta canónica**: se construye desde `service_candidate` / `normalized_service` + `domain_code` / `domain` + `category_name` / `category`.
- **Contexto auxiliar**: `problem_description` se conserva para trazabilidad y ranking, pero no forma parte del texto principal que se embebe.
- **Comportamiento ante falla de RPC o embeddings**: fail-fast, sin fallback local a búsquedas legacy.
- **Signals opcionales**: `ai-clientes` puede adjuntar `signals` en el contexto para reforzar el reranking y la compatibilidad semántica sin alterar el embedding base.

## 🗃️ Base de Datos Optimizada

### Índices Especializados

```sql
-- Índice vectorial / semántico
CREATE INDEX idx_search_vector_gin
ON provider_search_index USING GIN(search_vector);

-- Búsquedas compuestas para filtros
CREATE INDEX idx_city_active
ON provider_search_index(city_normalized, is_active);
```

### Funciones de Búsqueda

```sql
-- Búsqueda vectorial optimizada
SELECT * FROM match_provider_services(
    query_embedding := :embedding,
    match_count := 30,
    city_filter := '%Quito%'
);
```

## 🔄 Integración con AI Clientes

### Modo de uso

```python
import httpx

async def search_in_service(query: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://search-token:8000/api/v1/search",
            json={
                "query": query,
                "limit": 5
            }
        )
        return response.json()
```

## 📊 Métricas y Monitoreo

### Métricas Disponibles

```bash
GET /api/v1/metrics
```

- Búsquedas totales
- Cache hit ratio
- Uso de IA
- Tiempos de respuesta
- Consultas populares

### Métricas de Prometheus

```bash
# Disponible en :9091/metrics
curl http://localhost:9091/metrics
```

## 🔧 Configuración

### Variables Clave

| Variable | Default | Descripción |
|----------|---------|-------------|
| `DATABASE_URL` | - | URL de PostgreSQL |
| `REDIS_URL` | `redis://localhost:6379/1` | URL de Redis |
| `OPENAI_API_KEY` | - | API Key de OpenAI (obligatoria) |
| `MAX_SEARCH_RESULTS` | `20` | Máximo de resultados |
| `CACHE_TTL_SECONDS` | `300` | TTL del caché |

### Performance Tuning

```python
# PostgreSQL settings (postgresql.conf)
shared_preload_libraries = 'pg_trgm'
random_page_cost = 1.1  # SSD
effective_cache_size = '4GB'
work_mem = '64MB'
```

## 🧪 Testing

```bash
# Tests unitarios
python -m pytest tests/

# Tests de integración
python -m pytest tests/integration/

# Tests de carga
python -m pytest tests/load/
```

## 🚀 Despliegue

### Producción

```bash
# Build
docker build -t tinkubot/search-token .

# Run
docker run -d \
  --name search-token \
  -p 8000:8000 \
  -e DATABASE_URL=$DATABASE_URL \
  -e REDIS_URL=$REDIS_URL \
  tinkubot/search-token
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: search-token
spec:
  replicas: 3
  selector:
    matchLabels:
      app: search-token
  template:
    metadata:
      labels:
        app: search-token
    spec:
      containers:
      - name: search-token
        image: tinkubot/search-token:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: tinkubot-secrets
              key: database-url
```

## 🔍 Troubleshooting

### Problemas Comunes

**Búsquedas lentas (> 500ms)**
```bash
# Verificar índices
psql -d tinkubot -c "\d+ provider_search_index"

# Rebuild índices
psql -d tinkubot -c "REINDEX INDEX provider_search_index_pkey;"
```

**Cache no funciona**
```bash
# Verificar Redis
curl http://localhost:8000/api/v1/cache/info

# Limpiar caché
curl -X DELETE http://localhost:8000/api/v1/cache/clear
```

**Embeddings no disponibles**
```bash
# Verificar API Key
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
     https://api.openai.com/v1/models
```

## 📈 Mejoras Futuras

- [ ] Búsqueda por geolocalización
- [ ] Aprendizaje automático de preferencias
- [ ] Búsqueda por disponibilidad en tiempo real
- [ ] Optimización de recuperación vectorial
- [ ] Sistema de recomendaciones personalizado

## 📝 Licencia

MIT License - ver archivo LICENSE
