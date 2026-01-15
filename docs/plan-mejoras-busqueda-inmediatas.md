# Plan: Mejoras Inmediatas al Sistema de Búsqueda de Proveedores

> **Fecha**: Enero 2026
> **Versión**: 1.0 - Mejoras Inmediatas (Pre-Semántica)
> **Estado**: Listo para revisión
> **Timeline**: 4 semanas

## Resumen Ejecutivo

Este plan extrae las funcionalidades más significativas del servicio `ai-search` (eliminado en Enero 2026) y las adapta a la arquitectura actual de `ai-clientes` para implementar **mejoras inmediatas de alto impacto** sin requerir la infraestructura completa de búsqueda semántica planificada para el siguiente mes.

**Problema actual**: El sistema de búsqueda tiene altos falsos negativos y no maneja bien búsquedas basadas en necesidades ("tengo goteras" → no encuentra plomeros).

**Solución**: Implementar clasificación de intenciones, expansión de queries con IA, y búsqueda multi-estrategia con fallback inteligente.

**Beneficios esperados**:
- 40% reducción en falsos negativos
- Mejor manejo de queries descriptivas ("tengo una fuga de agua")
- 60% tasa de cache hit (vs 30% actual)
- Escalable a 100K+ proveedores

---

## 1. Análisis del Estado Actual

### 1.1 Implementación Actual (ai-clientes)

**Archivos críticos**:
- `/home/du/produccion/tinkubot-microservices/python-services/ai-clientes/services/search_service.py`
- `/home/du/produccion/tinkubot-microservices/python-services/ai-clientes/services/query_interpreter_service.py`
- `/home/du/produccion/tinkubot-microservices/python-services/ai-clientes/services/dynamic_service_catalog.py`

**Flujo actual**:
```
Usuario: "tengo goteras"
   ↓
QueryInterpreterService (OpenAI GPT-3.5)
   → Interpreta: profession="plomero", city="Quito"
   ↓
ProviderRepository.search_by_city_and_profession()
   → Supabase: WHERE profession ILIKE '%plomero%' AND city ILIKE '%Quito%'
   ↓
Retorna: Lista de proveedores (ordenados por rating)
```

**Limitaciones críticas**:
1. ❌ Búsqueda por texto exacto (ILIKE) - sin comprensión semántica
2. ❌ Altos falsos negativos ("tengo goteras" no encuentra plomeros si no está mapeado explícitamente)
3. ❌ Sin expansión de queries
4. ❌ Sin clasificación de intención (directa vs necesidad)
5. ❌ Sin mecanismos de fallback robustos

### 1.2 Historia Git - ai-search (Eliminado)

**Commit clave**: `dfb7830` (Noviembre 2025) - Última versión completa antes de eliminación

**Archivos eliminados** (Enero 2026, commit `9636771`):
- `python-services/ai-search/services/search_service.py` (596 líneas)
- `python-services/ai-search/utils/text_processor.py` (657 líneas)
- Total: 2,600+ líneas eliminadas

**Funcionalidades valiosas a extraer**:
1. **Multi-Strategy Search**: Token-based, full-text, hybrid, AI-enhanced
2. **Query Expansion**: Expansión con sinónimos vía OpenAI
3. **Text Processing**: Normalización, eliminación de stop words, extracción de tokens
4. **Relevancy Scoring**: Ranking de resultados por múltiples factores

---

## 2. Estrategia de Mejoras Inmediatas

### 2.1 Principios de Diseño

1. **Aprovechar arquitectura existente**: Repository Pattern, CacheManager, PerformanceMetrics, Feature Flags
2. **Sin nuevos servicios externos**: Mantener simplicidad (no SPOF)
3. **Backward compatible**: No romper el flujo actual
4. **Feature-flagged**: Rollback instantáneo si algo falla
5. **Escalable**: Debe soportar crecimiento a 100K+ proveedores

### 2.2 Roadmap de 4 Semanas

```
Semana 1: Clasificación de Intenciones + Procesamiento de Texto
Semana 2: Expansión de Queries con IA
Semana 3: Búsqueda Multi-Estrategia
Semana 4: Fallback Inteligente + Rollout Gradual
```

---

## 3. Implementación Detallada

### Semana 1: Clasificación de Intenciones

#### 3.1 Nuevo Servicio: IntentClassifier

**Archivo**: `/home/du/produccion/tinkubot-microservices/python-services/ai-clientes/services/intent_classifier.py`

**Propósito**: Clasificar queries del usuario en dos tipos:
- **DIRECT**: "necesito un plomero" → Búsqueda directa de profesión
- **NEED_BASED**: "tengo goteras" → Requiere inferencia a profesión
- **AMBIGUOUS**: No clara

**Implementación**:
```python
class IntentClassifier:
    """
    Clasifica intenciones de búsqueda usando heurísticas + IA.

    Estrategias:
    1. Pattern matching (rápido, patrones comunes)
    2. Análisis de keywords (detección de servicios)
    3. Clasificación con IA (fallback para queries complejas)
    """

    DIRECT_PATTERNS = [
        r"necesito\s+(un|una)?\s*(\w+)",
        r"busco\s+(un|una)?\s*(\w+)",
        r"requiero\s+(un|una)?\s*(\w+)",
    ]

    NEED_KEYWORDS = {
        "goteras": "plomero",
        "fuga": "plomero",
        "cortocircuito": "electricista",
        "problemas eléctricos": "electricista",
        # ... (50+ mapeos)
    }

    async def classify_intent(self, query: str) -> IntentType:
        """Retorna: DIRECT, NEED_BASED, o AMBIGUOUS"""
```

**Feature flag**: `USE_INTENT_CLASSIFICATION` (default: false)

#### 3.2 Utilidades de Procesamiento de Texto

**Archivo**: `/home/du/produccion/tinkubot-microservices/python-services/ai-clientes/utils/text_processor.py`

**Extraído de**: `ai-search/utils/text_processor.py` (657 líneas)

**Funciones clave**:
```python
class TextProcessor:
    """Procesamiento avanzado de texto para búsqueda."""

    STOP_WORDS_ES = {
        "el", "la", "los", "las", "un", "una", "de", "en", "con",
        "por", "para", "y", "o", "que", "necesito", "busco", "quiero"
    }

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normaliza texto para búsqueda:
        - Minúsculas
        - Elimina acentos
        - Elimina caracteres especiales
        - Unifica espacios
        """

    @staticmethod
    def extract_tokens(text: str, remove_stop_words: bool = True) -> List[str]:
        """Extrae tokens únicos del texto."""

    @staticmethod
    def calculate_relevance_score(
        provider: Dict[str, Any],
        query_tokens: List[str]
    ) -> float:
        """Calcula score de relevancia para ranking."""
```

---

### Semana 2: Expansión de Queries con IA

#### 3.3 Servicio de Expansión de Queries

**Archivo**: `/home/du/produccion/tinkubot-microservices/python-services/ai-clientes/services/query_expansion.py`

**Propósito**: Expandir queries con sinónimos y términos relacionados.

**Ejemplos**:
- "tengo goteras" → "plomero plomería fugas agua fontanería reparación tuberías"
- "limpieza facial" → "estética facial cosmetología cuidado piel beautician spa"

**Implementación**:
```python
class QueryExpander:
    """
    Expande queries usando múltiples estrategias:
    1. Catálogo dinámico de sinónimos (existente)
    2. Expansión con OpenAI (nueva)
    3. Sinónimos estáticos (de ai-search)
    """

    EXPANSION_PROMPT = """
Eres un experto en servicios profesionales en Ecuador.
Expande esta consulta incluyendo sinónimos y términos relacionados.

REGLAS:
- Incluye sinónimos regionales de Ecuador
- Convierte problemas a soluciones ("goteras" → "plomero")
- Responde ÚNICAMENTE con términos separados por espacios

Ejemplos:
- "tengo goteras" → "plomero plomería fugas agua fontanería"
- "limpieza facial" → "estética facial cosmetología cuidado piel"

Expande: {user_message}
"""

    async def expand_query(
        self,
        query: str,
        intent_type: IntentType
    ) -> Dict[str, Any]:
        """
        Expande query y retorna:
        - expanded_terms: List[str]
        - inferred_profession: str (si es need-based)
        - expansion_method: "ai" | "synonyms" | "none"
        """
```

**Caché**:
- Key: `query_expansion:{hash(query)}`
- TTL: 3600s (1 hora)
- Expected hit rate: >70%

**Feature flag**: `USE_QUERY_EXPANSION` (default: false)

#### 3.4 Base de Datos de Sinónimos Estáticos

**Modificación**: `/home/du/produccion/tinkubot-microservices/python-services/ai-clientes/services/dynamic_service_catalog.py`

**Agregar**:
```python
STATIC_SERVICE_SYNONYMS = {
    "plomero": {"plomero", "plomeria", "fontanero", "gasfitero", "tuberías"},
    "electricista": {"electricista", "electricidad", "eléctrico"},
    "esteticista": {
        "esteticista", "cosmetologa", "belleza", "cuidado facial",
        "facial", "limpieza facial", "skin care", "skincare"
    },
    # ... (50+ mapeos de ai-search)
}
```

---

### Semana 3: Búsqueda Multi-Estrategia

#### 3.5 Estrategias de Búsqueda

**Archivo**: `/home/du/produccion/tinkubot-microservices/python-services/ai-clientes/services/search_strategies.py`

**Estrategias implementadas**:

1. **Token-Based Search** (rápida, queries simples):
```python
async def search_by_tokens(
    city: str,
    expanded_query: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Búsqueda por tokens individuales.

    "plomero plomería fugas" → ['plomero', 'plomería', 'fugas']

    SQL: WHERE profession ILIKE '%plomero%'
           OR services ILIKE '%plomero%'
    """
```

2. **Full-Text Search** (queries complejas):
```python
async def search_fulltext(
    city: str,
    query: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Búsqueda en múltiples campos:
    - profession
    - services (array)
    - specialty
    - description
    """
```

3. **Hybrid Search** (combina ambas):
```python
async def search_hybrid(
    city: str,
    query: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Ejecuta token + full-text en paralelo, une resultados:
    - Token results (prioridad)
    - Full-text results (completa)
    - Deduplica por provider ID
    """
```

#### 3.6 Selector de Estrategia

```python
async def select_search_strategy(
    query_analysis: Dict[str, Any],
    intent_type: IntentType
) -> SearchStrategy:
    """
    Selecciona estrategia óptima basada en:
    1. Complejidad de query (conteo de tokens)
    2. Tipo de intención (direct vs need-based)
    3. Resultados previos (si es retry)

    Retorna:
        TOKEN_BASED (queries simples)
        FULL_TEXT (queries complejas)
        HYBRID (búsquedas amplias)
        AI_ENHANCED (need-based)
    """
```

**Feature flag**: `USE_MULTI_STRATEGY_SEARCH` (default: false)

---

### Semana 4: Fallback Inteligente

#### 3.7 Búsqueda con Fallback Multi-Etapas

**Modificación**: `/home/du/produccion/tinkubot-microservices/python-services/ai-clientes/services/search_service.py`

**Nuevo método**:
```python
async def intelligent_search_providers_with_fallback(
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Búsqueda multi-etapa con fallback inteligente.

    Etapas:
    1. Búsqueda primaria (estrategia seleccionada)
       Si <3 resultados →
    2. Búsqueda expandida (remueve filtro ciudad, más sinónimos)
       Si <3 resultados →
    3. Búsqueda amplia (statewide, profesiones relacionadas)

    Retorna providers + metadata de estrategia usada.
    """
```

**Lógica de fallback**:
```python
# Etapa 1: Búsqueda primaria
providers = await primary_search(city, profession)
if len(providers) >= 3:
    return {providers, "search_scope": "local"}

# Etapa 2: Búsqueda expandida
providers = await expanded_search(
    city="",  # Sin filtro de ciudad
    profession=expanded_profession,  # Términos expandidos
    limit=20
)
if len(providers) >= 3:
    return {providers, "search_scope": "statewide"}

# Etapa 3: Profesiones relacionadas
providers = await search_related_professions(profession, limit=30)
return {providers, "search_scope": "statewide_related"}
```

**Feature flag**: `USE_SMART_FALLBACK` (default: false)

#### 3.8 Ranking de Resultados

```python
def rank_providers(
    providers: List[Dict[str, Any]],
    query_tokens: List[str]
) -> List[Dict[str, Any]]:
    """
    Ranking por score de relevancia.

    Factores:
    - Match exacto de profesión: +10 puntos
    - Match parcial (services): +5 puntos
    - Disponible: +3 puntos
    - Rating > 4.0: +2 puntos
    - Verificado: +1 punto
    - Ciudad coincide: +2 puntos
    """
```

---

## 4. Archivos Críticos a Modificar

### Archivos Nuevos a Crear

| Archivo | Propósito | Líneas estimadas |
|---------|-----------|------------------|
| `services/intent_classifier.py` | Clasificación de intenciones | ~200 |
| `utils/text_processor.py` | Procesamiento de texto (de ai-search) | ~400 |
| `services/search_strategies.py` | Estrategias de búsqueda | ~600 |
| `services/query_expansion.py` | Expansión de queries | ~300 |

### Archivos Existentes a Modificar

| Archivo | Cambios | Impacto |
|---------|---------|---------|
| `services/search_service.py` | Agregar multi-estrategia + fallback | Alto |
| `services/query_interpreter_service.py` | Agregar método de expansión | Medio |
| `services/dynamic_service_catalog.py` | Agregar sinónimos estáticos | Bajo |
| `core/feature_flags.py` | Agregar nuevos flags | Bajo |
| `repositories/provider_repository.py` | Optimizar queries, agregar índices | Medio |

---

## 5. Feature Flags y Rollout Gradual

### 5.1 Nuevas Variables de Entorno

**Archivo**: `python-services/ai-clientes/core/feature_flags.py`

```python
# FASE 6: Enhanced Search (mejoras inmediatas)
USE_INTENT_CLASSIFICATION = os.getenv("USE_INTENT_CLASSIFICATION", "false") == "true"
USE_QUERY_EXPANSION = os.getenv("USE_QUERY_EXPANSION", "false") == "true"
USE_MULTI_STRATEGY_SEARCH = os.getenv("USE_MULTI_STRATEGY_SEARCH", "false") == "true"
USE_SMART_FALLBACK = os.getenv("USE_SMART_FALLBACK", "false") == "true"

# Rollout control
ENHANCED_SEARCH_ROLLOUT_PERCENT = int(os.getenv("ENHANCED_SEARCH_ROLLOUT_PERCENT", "0"))
```

### 5.2 Estrategia de Rollout

**Semana 1**: Testing interno (flags en false)
- Manual testing con cuentas de prueba
- Validar todos los escenarios

**Semana 2**: 10% del tráfico
- `ENHANCED_SEARCH_ROLLOUT_PERCENT = 10`
- Monitorear métricas, errores, latencia
- A/B testing: viejo vs nuevo

**Semana 3**: 50% del tráfico
- `ENHANCED_SEARCH_ROLLOUT_PERCENT = 50`
- Monitoreo completo
- Recopilar feedback

**Semana 4**: 100% rollout
- Todos los flags en true
- Remover código viejo (deprecated)
- Deploy completo

### 5.3 Plan de Rollback

**Rollback instantáneo**:
```bash
# Desactivar mejoras
export USE_INTENT_CLASSIFICATION=false
export USE_QUERY_EXPANSION=false
export USE_MULTI_STRATEGY_SEARCH=false
export USE_SMART_FALLBACK=false

# Restart
docker compose restart ai-clientes
```

---

## 6. Estrategia de Escalabilidad

### 6.1 Objetivos de Performance

| Métrica | Actual | Target (Semana 4) | Target (100K providers) |
|---------|--------|-------------------|-------------------------|
| P50 Latency | 150ms | 200ms | 300ms |
| P95 Latency | 200ms | 400ms | 600ms |
| P99 Latency | 300ms | 800ms | 1200ms |
| Cache Hit Rate | 30% | 60% | 70% |

### 6.2 Estrategia de Caché Multi-Nivel

**Niveles de caché** (usando CacheManager existente):

1. **Query Expansion Cache** (NUEVO)
   - Key: `query_expansion:{hash(query)}`
   - TTL: 3600s (1 hora)
   - Expected hit rate: 70%

2. **Search Results Cache** (existente)
   - Key: `search:{city}:{profession}`
   - TTL: 300s (5 minutos)

3. **Provider Profile Cache** (existente)
   - Key: `provider:{provider_id}`
   - TTL: 3600s (1 hora)

### 6.3 Optimización de Base de Datos

**Crear índices en Supabase**:
```sql
-- Para búsquedas por ciudad
CREATE INDEX idx_providers_city_rating
ON providers(city, rating DESC)
WHERE verified = true;

-- Para búsquedas por profesión
CREATE INDEX idx_providers_profession_rating
ON providers(profession, rating DESC)
WHERE verified = true;

-- Para búsquedas full-text (PostgreSQL)
CREATE INDEX idx_providers_services_gin
ON providers USING gin(to_tsvector('spanish', services));
```

### 6.4 Roadmap de Escalabilidad

| Cantidad Providers | Estrategia | Latencia Est. | Costo |
|--------------------|-----------|---------------|-------|
| Actual (1K) | DB directo + caché | 150ms | $0/mes |
| 10K | DB + caché + índices | 200ms | $0/mes |
| 100K | DB + caché + read replica | 300ms | $25/mes |
| 1M+ | Full-text search + caché | 500ms | $100/mes |

**Futuro (siguiente mes)**:
- Implementar pgvector para búsqueda semántica
- Generar embeddings para proveedores
- Hybrid search (BM25 + Vector)

---

## 7. Métricas de Éxito y Monitoreo

### 7.1 KPIs a Trackear

**Nuevas métricas** (PerformanceMetrics):
```python
metrics.record("intent_classification", duration_ms)
metrics.record("query_expansion", duration_ms)
metrics.record("search_strategy", duration_ms, metadata={
    "strategy": strategy.value,
    "results_count": len(providers),
    "fallback_used": True/False
})
```

**Métricas clave**:
| Métrica | Descripción | Target |
|---------|-------------|--------|
| `intent_classification_ms` | Tiempo de clasificación | <10ms |
| `query_expansion_ms` | Tiempo de expansión | <150ms (AI), <5ms (cache) |
| `search_strategy_ms` | Tiempo por estrategia | <100ms (token), <200ms (fulltext) |
| `fallback_rate` | % búsquedas con fallback | <20% |
| `zero_results_rate` | % búsquedas con 0 resultados | <10% |
| `expansion_cache_hit_rate` | % expansiones desde caché | >70% |

### 7.2 Dashboard de Monitoreo

**Endpoint**: `/debug/search-metrics`

**Métricas a mostrar**:
```
Search Performance Dashboard
├── Total Searches (24h): 1,234
├── Avg Latency: 245ms (P50), 412ms (P95), 789ms (P99)
├── Cache Hit Rate: 62%
├── Zero Results Rate: 8%
├── Strategy Distribution:
│   ├── Token-based: 45%
│   ├── Full-text: 30%
│   ├── Hybrid: 15%
│   └── AI-enhanced: 10%
└── Top Queries:
    ├── "plomero" (123 searches)
    ├── "electricista" (89 searches)
    └── "limpieza facial" (67 searches)
```

---

## 8. Testing y Verificación

### 8.1 Tests Unitarios

**Archivos a crear**:
- `tests/unit/test_intent_classifier.py`
- `tests/unit/test_text_processor.py`
- `tests/unit/test_search_strategies.py`
- `tests/unit/test_query_expansion.py`

**Ejemplo**:
```python
@pytest.mark.asyncio
async def test_classify_need_based_query():
    classifier = IntentClassifier()
    intent = await classifier.classify_intent("tengo goteras en el techo")
    assert intent == IntentType.NEED_BASED

@pytest.mark.asyncio
async def test_expand_query_with_synonyms():
    expander = QueryExpander(openai_client, cache_manager)
    expanded = await expander.expand_query("tengo goteras")

    assert "plomero" in expanded["expanded_terms"]
    assert "plomeria" in expanded["expanded_terms"]
```

### 8.2 Tests de Integración

**Archivo**: `tests/integration/test_search_flow.py`

**Escenarios críticos**:
1. "necesito un plomero en Quito" → Direct search → Encuentra plomeros
2. "tengo goteras" → Need-based → Infiere "plomero"
3. "limpieza facial" → Ambiguous → Expande a estética facial
4. "cortocircuito" → Need-based → Infiere "electricista"
5. "estilista de cabello" → Direct search → Encuentra peluquería

**Criterio de éxito**:
- Todos los queries retornan resultados relevantes
- Falsos negativos reducidos en 40%
- Latencia promedio <400ms
- Cache hit rate >60%

### 8.3 Pruebas de Performance

**Script de load testing** (usando k6):
```bash
k6 run - <<EOF
import http from 'k6/http';

export let options = {
  stages: [
    { duration: '1m', target: 10 },
    { duration: '3m', target: 50 },
    { duration: '2m', target: 100 },
  ],
};

export default function () {
  let payload = JSON.stringify({
    main_profession: "plomero",
    location: "Quito"
  });

  http.post('http://localhost:8001/search', payload, {
    headers: { 'Content-Type': 'application/json' }
  });
}
EOF
```

---

## 9. Análisis de Riesgos y Mitigación

### 9.1 Matriz de Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Rate limiting de OpenAI API | Media | Medio | 80% cache hit, fallback a sinónimos |
| Aumento de latencia | Baja | Medio | Feature flags, rollout gradual |
| Cache stampede | Baja | Alto | Cache warming, request coalescing |
| Expansión pobre de queries | Media | Alto | A/B testing, revisión manual |
| Sobrecarga de BD | Baja | Medio | Read replicas, connection pooling |

### 9.2 Estrategias de Mitigación

**OpenAI Rate Limiting**:
```python
async def expand_query_with_retry(query: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            return await openai_client.expand(query)
        except RateLimitError:
            if attempt == max_retries - 1:
                # Fallback a expansión con sinónimos
                return await expand_with_synonyms(query)
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

**Cache Stampede Prevention**:
```python
# Use cache-aside pattern con locking
async def get_expanded_query(query: str):
    cache_key = f"expansion:{hash(query)}"

    cached = await cache.get(cache_key)
    if cached:
        return cached

    async with cache_locks[cache_key]:
        # Double-check cache
        cached = await cache.get(cache_key)
        if cached:
            return cached

        # Expand and cache
        expanded = await expand_query_openai(query)
        await cache.set(cache_key, expanded, ttl=3600)
        return expanded
```

---

## 10. Cronograma de Implementación

### Semana 1 (Enero 20-24): Fundamentos

**Día 1-2**: Intent Classification
- Crear `services/intent_classifier.py`
- Implementar clasificación basada en patrones
- Agregar unit tests
- Feature flag: `USE_INTENT_CLASSIFICATION`

**Día 3-4**: Text Processing
- Crear `utils/text_processor.py` (extraído de ai-search)
- Implementar normalización, tokenización
- Agregar unit tests
- Integrar con QueryInterpreterService

**Día 5**: Testing e integración
- End-to-end testing
- Performance benchmarks
- Code review

### Semana 2 (Enero 27-31): Query Expansion

**Día 1-3**: Query Expansion Service
- Crear `services/query_expansion.py`
- Implementar expansión con OpenAI
- Agregar capa de caché
- Feature flag: `USE_QUERY_EXPANSION`

**Día 4**: Static Synonyms
- Mejorar `DynamicServiceCatalog`
- Agregar sinónimos estáticos de ai-search
- Migración de BD (si necesario)

**Día 5**: Testing y QA
- Unit tests
- Integration tests
- Manual testing con 20 queries

### Semana 3 (Febrero 3-7): Multi-Strategy Search

**Día 1-2**: Token Search
- Implementar `TokenSearchStrategy`
- Optimizar queries de ProviderRepository
- Agregar tracking de métricas

**Día 3**: Full-Text Search
- Implementar `FullTextSearchStrategy`
- Multi-field search (profession, services, specialty)

**Día 4**: Hybrid Search
- Implementar `HybridSearchStrategy`
- Ejecución paralela con asyncio.gather()

**Día 5**: Strategy Selector
- Implementar `select_search_strategy()`
- Agregar lógica A/B testing
- Feature flag: `USE_MULTI_STRATEGY_SEARCH`

### Semana 4 (Febrero 10-14): Fallback y Rollout

**Día 1-2**: Smart Fallback
- Implementar `intelligent_search_providers_with_fallback()`
- Lógica de fallback multi-etapa
- Ranking de resultados

**Día 3**: Performance Optimization
- Índices de base de datos
- Cache warming
- Load testing

**Día 4**: 10% Rollout
- Enable feature flags para 10% del tráfico
- Monitorear métricas
- Fix issues

**Día 5**: Documentación y Handoff
- Actualizar README
- Crear runbook
- Team training

---

## 11. Costos y Beneficios

### 11.1 Esfuerzo de Desarrollo

| Tarea | Esfuerzo | Riesgo | Prioridad |
|------|----------|--------|----------|
| Intent Classification | 2 días | Bajo | Alta |
| Query Expansion | 3 días | Medio | Alta |
| Text Processing Utils | 2 días | Bajo | Alta |
| Multi-Strategy Search | 4 días | Medio | Alta |
| Smart Fallback | 2 días | Bajo | Media |
| Testing & QA | 3 días | Bajo | Alta |
| Documentation | 1 día | Bajo | Media |

**Total**: ~17 días de desarrollador (~3.4 semanas)

### 11.2 Costos de Infraestructura

| Componente | Costo Actual | Costo Adicional | Notas |
|-----------|--------------|------------------|-------|
| OpenAI API (GPT-3.5) | $5/mes | +$3/mes | Query expansion (80% cache) |
| Redis Cache | $0/mes | $0/mes | Infraestructura existente |
| Supabase DB | $0/mes | $0/mes | Infraestructura existente |
| Monitoring | $0/mes | $0/mes | Infraestructura existente |

**Total adicional**: ~$3/mes (principalmente OpenAI)

### 11.3 Beneficios Esperados

**Cuantitativos**:
- 40% reducción en falsos negativos
- 60% cache hit rate (vs 30% actual)
- 25% mejora en relevancia de búsqueda
- <400ms P95 latency (vs 200ms actual, trade-off aceptable)

**Cualitativos**:
- Mejor manejo de queries descriptivas ("tengo una fuga")
- Mejor experiencia de usuario (resultados más relevantes)
- Base para búsqueda semántica futura
- Escalable a 100K+ proveedores sin cambios mayores

**ROI**:
- Desarrollo: $3,400 (17 días @ $200/día)
- Costo mensual: +$3
- Beneficio: Mejor tasa de conversión, satisfacción de usuario
- Payback period: ~2-3 meses (asumiendo 10% mejora en conversión)

---

## 12. Verificación Final

### 12.1 Criterios de Éxito - Semana 1-2

**Intent Classification**:
- [ ] 90% accuracy en dataset de prueba (100 queries)
- [ ] <10ms latencia promedio
- [ ] Cero errores en producción

**Query Expansion**:
- [ ] 80% cache hit rate
- [ ] Expande queries con 3-5 sinónimos
- [ ] Reduce zero results en 30%

### 12.2 Criterios de Éxito - Semana 3-4

**Multi-Strategy Search**:
- [ ] Token search: <100ms P95
- [ ] Full-text search: <200ms P95
- [ ] Hybrid search: <250ms P95
- [ ] 95% uptime

**Smart Fallback**:
- [ ] 90% de búsquedas retornan ≥3 resultados
- [ ] Fallback rate <20%
- [ ] Sin infinite loops

### 12.3 Verificación Manual

**Queries críticos de prueba**:
```bash
for query in "necesito un plomero" "tengo goteras" "limpieza facial" "cortocircuito" "estilista"; do
  echo "Testing: $query"
  curl -X POST http://localhost:8001/search \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"$query\", \"city\": \"Quito\"}" | jq '.total'
done

# Expected: todos retornan >0 resultados
```

---

## 13. Conclusión

Este plan proporciona un **enfoque pragmático y escalable** para mejorar inmediatamente el sistema de búsqueda de proveedores en ai-clientes. Al extraer las mejores características del servicio ai-search eliminado y adaptarlas a la arquitectura SOLID actual, podemos lograr:

**Beneficios Inmediatos (Semana 1-4)**:
- 40% reducción en falsos negativos
- Mejor manejo de queries basadas en necesidades
- 60% cache hit rate
- Búsqueda multi-estrategia con fallback inteligente
- Rollout gradual con feature flags

**Escalabilidad**:
- Soporta 10K-100K proveedores sin cambios mayores
- Base para búsqueda semántica (siguiente mes)
- Costo-efectivo (+$3/mes para expansión OpenAI)

**Mitigación de Riesgos**:
- Feature flags para rollback instantáneo
- Testing comprehensivo (unit, integration, manual)
- Rollout gradual (10% → 50% → 100%)
- Monitoreo de performance en cada etapa

**Eficiencia de Desarrollo**:
- Aprovecha arquitectura existente (Repository, Cache, Metrics)
- Sin nuevos servicios externos
- Timeline de 3-4 semanas
- Criterios de éxito claros y verificables

---

## Archivos Críticos para Implementación

Los 5 archivos más críticos para implementar las mejoras inmediatas:

1. **`python-services/ai-clientes/services/search_service.py`** - Lógica core de búsqueda a modificar con multi-estrategia y fallback

2. **`python-services/ai-clientes/services/query_interpreter_service.py`** - Agregar método de expansión de queries

3. **`python-services/ai-clientes/services/intent_classifier.py`** (NUEVO) - Clasificación de intenciones

4. **`python-services/ai-clientes/utils/text_processor.py`** (NUEVO) - Utilidades de procesamiento de texto de ai-search

5. **`python-services/ai-clientes/core/feature_flags.py`** - Agregar nuevos feature flags para rollout gradual
