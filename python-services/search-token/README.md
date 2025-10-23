# Search Service

Microservicio especializado en búsqueda ultra-rápida de proveedores para TinkuBot.

## 🚀 Características

- **Búsqueda por tokens**: Ultra-rápida (< 50ms) usando índices optimizados
- **Búsqueda full-text**: Para consultas complejas y descriptivas
- **Búsqueda híbrida**: Combina múltiples estrategias
- **Mejora con IA**: OpenAI integrada para consultas ambiguas
- **Caché inteligente**: Redis para respuestas instantáneas
- **Orquestación automática**: Selecciona la mejor estrategia según la consulta
- **Normalización avanzada**: Texto sin acentos, minúsculas, sin caracteres especiales

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
                       │  (opcional)     │
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
docker-compose up -d search-token
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
    "available_only": true,
    "min_rating": 4.0,
    "city": "Quito"
  },
  "limit": 10,
  "use_ai_enhancement": true
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

## 🎯 Estrategias de Búsqueda

### 1. Token-Based (por defecto)
- **Velocidad**: < 50ms
- **Ideal**: "médico quito", "plomero", "abogado"
- **Cómo funciona**: Busca coincidencias exactas de tokens normalizados

### 2. Full-Text
- **Velocidad**: 100-200ms
- **Ideal**: "necesito alguien que arregle la tubería de la cocina"
- **Cómo funciona**: Búsqueda semántica con PostgreSQL tsvector

### 3. Hybrid
- **Velocidad**: 100-300ms
- **Ideal**: Consultas con múltiples interpretaciones
- **Cómo funciona**: Combina resultados de ambas estrategias

### 4. AI-Enhanced
- **Velocidad**: 300-600ms
- **Ideal**: "ayuda con algo legal", "tengo un problema técnico"
- **Cómo funciona**: OpenAI mejora la consulta antes de buscar

## 🗃️ Base de Datos Optimizada

### Índices Especializados

```sql
-- Búsqueda por contención de arrays
CREATE INDEX idx_profession_tokens_gin
ON provider_search_index USING GIN(profession_tokens);

-- Búsqueda full-text
CREATE INDEX idx_search_vector_gin
ON provider_search_index USING GIN(search_vector);

-- Búsquedas compuestas
CREATE INDEX idx_city_active
ON provider_search_index(city_normalized, is_active);
```

### Funciones de Búsqueda

```sql
-- Búsqueda optimizada por tokens
SELECT * FROM search_providers_by_tokens(
    ARRAY['medico', 'doctor'],
    'Quito',
    10, 0
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
                "use_ai_enhancement": True,
                "limit": 5
            }
        )
        return response.json()
```

### Flujo de Decisión

1. **Consulta clara** → Token-based (instantáneo)
2. **Consulta ambigua** → AI-enhanced (inteligente)
3. **Consulta compleja** → Hybrid (completo)

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
| `OPENAI_API_KEY` | - | API Key de OpenAI (opcional) |
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

**IA no mejora consultas**
```bash
# Verificar API Key
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
     https://api.openai.com/v1/models
```

## 📈 Mejoras Futuras

- [ ] Búsqueda por geolocalización
- [ ] Aprendizaje automático de preferencias
- [ ] Búsqueda por disponibilidad en tiempo real
- [ ] Integración con más APIs de IA
- [ ] Sistema de recomendaciones personalizado

## 📝 Licencia

MIT License - ver archivo LICENSE