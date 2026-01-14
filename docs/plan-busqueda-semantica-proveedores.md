# Plan: Búsqueda Semántica de Proveedores con Hugging Face

## Resumen Ejecutivo

Implementar búsqueda semántica para mejorar la interpretación del lenguaje natural de clientes y encontrar mejores matches con proveedores, usando **sentence-transformers** pre-entrenados vía **Hugging Face Jobs**.

**Enfoque**: Quick win - 1-2 semanas de implementación
**Prioridad**: Mejor interpretación del lenguaje del cliente ("tengo goteras" → "plomero")
**Infraestructura**: Hugging Face Jobs (cloud) para inferencia

---

## Problema Actual

### Búsqueda Actual (ai-proveedores/services/search_service.py:14-50)
```python
# Solo usa matching por texto con ilike
query = supabase.table("providers").select("*").eq("verified", True)
query = query.or_("profession.ilike.*{profesion}*")
```

**Limitaciones**:
- ❌ No entiende lenguaje natural ("goteras" ≠ "plomero")
- ❌ No encuentra proveedores semánticamente similares
- ❌ Solo matching exacto de palabras

### Interpretación Actual (ai-clientes/services/search_service.py:177-278)
```python
# Usa QueryInterpreterService con OpenAI GPT-3.5
interpretation = await query_interpreter_svc.interpret_query(...)
providers = await provider_repo.search_by_city_and_profession(...)
```

**Limitaciones**:
- ⚠️ Interpreta bien, pero la búsqueda sigue siendo por texto exacto
- ⚠️ No hay scoring de similitud o ranking semántico

---

## Solución Propuesta

### Arquitectura

```
Cliente: "tengo goteras"
   ↓
AI Clientes: QueryInterpreterService (OpenAI) → "plomero"
   ↓
AI Proveedores: SemanticSearchService
   ├─ Generar embedding del query (HF Inference API)
   ├─ Buscar por similitud coseno en PostgreSQL + pgvector
   └─ Retornar proveedores ordenados por similitud
```

### Tecnologías

**Modelo**: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- 384 dimensiones (ligero)
- Multilingüe (español incluido)
- Gratis en HF Inference API

**Infraestructura**:
- **Entrenamiento/Embeddings**: Hugging Face Jobs (cloud GPU)
- **Inferencia**: HF Inference API + fallback local
- **Base de datos**: PostgreSQL con extensión **pgvector**
- **Caché**: Redis para embeddings de queries

---

## Fases de Implementación

### Fase 1: Setup de Base de Datos (Día 1-2)

**Archivo**: `python-services/migrations/add_semantic_search.sql` (NUEVO)

1. **Habilitar pgvector en Supabase**
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

2. **Crear tabla de embeddings**
   ```sql
   CREATE TABLE provider_embeddings (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       provider_id VARCHAR(255) UNIQUE REFERENCES providers(id),
       full_profile_embedding vector(384),
       embedding_model VARCHAR(100),
       created_at TIMESTAMP DEFAULT NOW()
   );

   CREATE INDEX idx_embeddings_hnsw
   ON provider_embeddings USING hnsw (full_profile_embedding vector_cosine_ops);
   ```

3. **Crear función de búsqueda semántica**
   ```sql
   CREATE OR REPLACE FUNCTION match_providers_semantic(
       query_embedding vector(384),
       target_city VARCHAR DEFAULT NULL,
       max_results INT DEFAULT 10
   ) RETURNS TABLE (...) AS $$
   BEGIN
       RETURN QUERY
       SELECT p.*, 1 - (pe.full_profile_embedding <=> query_embedding) as similarity
       FROM provider_embeddings pe
       JOIN providers p ON p.id = pe.provider_id
       WHERE p.verified = true AND p.available = true
       ORDER BY pe.full_profile_embedding <=> query_embedding
       LIMIT max_results;
   END;
   $$ LANGUAGE plpgsql;
   ```

4. **Crear tabla para recolectar datos de entrenamiento**
   ```sql
   CREATE TABLE search_interactions (
       id UUID PRIMARY KEY,
       original_query TEXT NOT NULL,
       interpreted_profession VARCHAR(255),
       providers_shown JSONB,
       provider_contacted VARCHAR(255),
       successful_match BOOLEAN,
       timestamp TIMESTAMP DEFAULT NOW()
   );
   ```

---

### Fase 2: Generar Embeddings (Día 3-4)

**Archivo**: `python-services/ai-proveedores/scripts/generate_embeddings.py` (NUEVO)

**Opción A: Local con sentence-transformers**
```python
from sentence_transformers import SentenceTransformer
import asyncio
from app.dependencies import get_supabase

model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
supabase = get_supabase()

async def generate_embeddings():
    # Obtener proveedores verificados
    result = supabase.table('providers').select('*').eq('verified', True).execute()
    providers = result.data

    for provider in providers:
        # Preparar texto
        text = f"Profesión: {provider['profession']}. Servicios: {provider['services']}. Ciudad: {provider['city']}."

        # Generar embedding
        embedding = model.encode(text, normalize_embeddings=True)

        # Guardar
        supabase.table('provider_embeddings').upsert({
            'provider_id': provider['id'],
            'full_profile_embedding': embedding.tolist(),
            'embedding_model': 'paraphrase-multilingual-MiniLM-L12-v2'
        }).execute()

asyncio.run(generate_embeddings())
```

**Opción B: Hugging Face Jobs (recomendado para datasets grandes)**
```bash
# Instalar HF CLI
pip install huggingface_hub
huggingface-cli login

# Submit job
python scripts/generate_embeddings.py --use-hf-jobs
```

---

### Fase 3: Servicio de Embeddings (Día 5)

**Archivo**: `python-services/ai-proveedores/services/embedding_service.py` (NUEVO)

```python
import os
import httpx
import numpy as np
from typing import Optional

class EmbeddingService:
    """Servicio para generar embeddings via HF Inference API."""

    def __init__(self):
        self.hf_token = os.getenv('HF_TOKEN')
        self.api_url = "https://api-inference.huggingface.co/models/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        self._local_model = None

    async def generate_embedding(self, text: str) -> Optional[np.ndarray]:
        """Generar embedding usando HF API (con fallback local)."""

        # Try HF API first
        if self.hf_token:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        self.api_url,
                        headers={"Authorization": f"Bearer {self.hf_token}"},
                        json={"inputs": text}
                    )
                    if response.status_code == 200:
                        embedding = np.array(response.json()[0])
                        return embedding / np.linalg.norm(embedding)
            except Exception as e:
                logger.warning(f"HF API failed: {e}")

        # Fallback to local model
        if self._local_model is None:
            from sentence_transformers import SentenceTransformer
            self._local_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

        return self._local_model.encode(text, normalize_embeddings=True)
```

---

### Fase 4: Búsqueda Semántica (Día 6-7)

**Archivo**: `python-services/ai-proveedores/services/search_service.py` (MODIFICAR)

```python
# Agregar nueva función
async def buscar_proveedores_semantic(
    query: str,
    ubicacion: Optional[str] = None,
    limite: int = 10
) -> List[Dict[str, Any]]:
    """
    Búsqueda semántica usando embeddings.

    Args:
        query: Query en lenguaje natural
        ubicacion: Ciudad opcional
        limite: Máximo de resultados

    Returns:
        Lista de proveedores ordenados por similitud
    """
    from services.embedding_service import embedding_service

    # 1. Generar embedding del query
    query_embedding = await embedding_service.generate_embedding(query)
    if query_embedding is None:
        # Fallback a búsqueda tradicional
        return await buscar_proveedores(query, ubicacion, limite)

    # 2. Buscar por similitud en PostgreSQL
    embedding_list = query_embedding.tolist()

    result = supabase.rpc('match_providers_semantic', {
        'query_embedding': str(embedding_list),
        'target_city': ubicacion,
        'max_results': limite
    }).execute()

    providers = result.data or []
    logger.info(f"Búsqueda semántica: {len(providers)} resultados para '{query}'")
    return providers

# Modificar función existente para usar semántica por defecto
async def buscar_proveedores(
    profesion: str,
    ubicacion: Optional[str] = None,
    limite: int = 10,
    usar_semantica: bool = True  # Nuevo parámetro
) -> List[Dict[str, Any]]:
    """Búsqueda de proveedores con soporte semántico."""

    if usar_semantica:
        try:
            return await buscar_proveedores_semantic(profesion, ubicacion, limite)
        except Exception as e:
            logger.warning(f"Búsqueda semántica falló: {e}, usando fallback")

    # Búsqueda tradicional (existente)
    # ... código actual ...
```

**Archivo**: `python-services/ai-proveedores/app/api/search.py` (MODIFICAR)

```python
@router.post("/intelligent-search")
async def intelligent_search_endpoint(payload: dict):
    """Endpoint mejorado con opción de búsqueda semántica."""

    # Extracción existente
    profesion = payload.get("profesion_principal", "")
    ubicacion = payload.get("ubicacion", "")
    necesidad_real = payload.get("necesidad_real", "")

    # Usar necesidad_real para búsqueda semántica si está disponible
    query = necesidad_real or profesion

    providers = await buscar_proveedores_semantic(
        query=query,
        ubicacion=ubicacion,
        limite=10
    )

    return {
        "ok": True,
        "providers": providers,
        "total": len(providers),
        "search_metadata": {
            "strategy": "semantic_search",
            "query_used": query
        }
    }
```

---

### Fase 5: Integración con AI Clientes (Día 8-9)

**Archivo**: `python-services/ai-clientes/services/search_service.py` (MODIFICAR)

En la función `intelligent_search_providers` (línea 177-278):

```python
async def intelligent_search_providers(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Búsqueda inteligente mejorada con búsqueda semántica."""

    # ... código existente para interpretación con IA ...

    # LUEGO de la interpretación de IA, usar búsqueda semántica
    try:
        # Llamar endpoint semántico de ai-proveedores
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PROVEEDORES_AI_SERVICE_URL}/intelligent-search",
                json={
                    "profesion_principal": interpreted_profession,
                    "ubicacion": interpreted_city,
                    "necesidad_real": need_summary  # ← Clave para semántica
                },
                timeout=10.0
            )

            if response.status_code == 200:
                return response.json()

    except Exception as e:
        logger.error(f"Error búsqueda semántica: {e}")

    # Fallback a búsqueda actual
    providers = await provider_repo.search_by_city_and_profession(...)
    # ... resto del código existente ...
```

**Agregar recolección de datos**:

```python
async def log_search_interaction(
    session_id: str,
    phone: str,
    query: str,
    providers: List,
    search_method: str = "semantic"
):
    """Registra interacción para dataset de entrenamiento futuro."""
    try:
        supabase.table('search_interactions').insert({
            'session_id': session_id,
            'client_phone': phone,
            'original_query': query,
            'interpreted_profession': query,  # Simplificado
            'providers_shown': [p['id'] for p in providers],
            'search_method': search_method
        }).execute()
    except Exception as e:
        logger.error(f"Error logging interaction: {e}")
```

---

### Fase 6: Testing y Deployment (Día 10-12)

**Tests manuales**:

```bash
# 1. Test de embedding generation
python scripts/generate_embeddings.py --test

# 2. Test de búsqueda semántica
curl -X POST "http://localhost:8002/intelligent-search" \
  -H "Content-Type: application/json" \
  -d '{
    "profesion_principal": "plomero",
    "ubicacion": "Quito",
    "necesidad_real": "tengo goteras en el techo"
  }'

# 3. Verificar que devuelve plomeros aunque no diga "plomero"
```

**Queries de prueba**:
- "tengo goteras" → debe encontrar plomeros
- "necesito arreglar el cortocircuito" → electricistas
- "mi perro necesita paseos" → veterinarios
- "se me rompió la cerca" → carpinteros/albañiles

**Deployment gradual**:
```python
# Feature flag en config
SEMANTIC_SEARCH_ENABLED = os.getenv('SEMANTIC_SEARCH_ENABLED', 'false') == 'true'

# En código, solo usar si está habilitado
if settings.semantic_search_enabled:
    return await buscar_proveedores_semantic(...)
```

---

## Archivos Críticos

### Crear (5 archivos)
1. **`python-services/migrations/add_semantic_search.sql`**
   - Tabla `provider_embeddings`
   - Índices HNSW
   - Función `match_providers_semantic()`

2. **`python-services/ai-proveedores/scripts/generate_embeddings.py`**
   - Script para generar embeddings de proveedores existentes
   - Usar sentence-transformers localmente o HF Jobs

3. **`python-services/ai-proveedores/services/embedding_service.py`**
   - `EmbeddingService` class
   - Integración con HF Inference API
   - Fallback local

4. **`python-services/ai-proveedores/.env.example`**
   - `HF_TOKEN=...`
   - `SEMANTIC_SEARCH_ENABLED=true`
   - `HF_MODEL_ID=...`

5. **`docs/semantic-search-guide.md`**
   - Documentación de arquitectura
   - Runbook de operaciones
   - Troubleshooting

### Modificar (3 archivos)
1. **`python-services/ai-proveedores/services/search_service.py`**
   - Agregar `buscar_proveedores_semantic()`
   - Modificar `buscar_proveedores()` para usar semántica

2. **`python-services/ai-proveedores/app/api/search.py`**
   - Endpoint `/intelligent-search` mejorado
   - Usar `necesidad_real` para query semántico

3. **`python-services/ai-clientes/services/search_service.py`**
   - Llamar endpoint semántico de ai-proveedores
   - Agregar logging a `search_interactions`

### Dependencias
**`python-services/ai-proveedores/requirements.txt`**
```
sentence-transformers==2.2.2
numpy==1.24.3
httpx==0.24.0
```

---

## Métricas de Éxito

### Baseline Actual
- Interpreta bien con OpenAI (~70% precisión)
- Búsqueda por texto exacto (ilike)
- Muchos falsos negativos (no encuentra proveedores válidos)

### Objetivos Week 1
- **Interpretación semántica**: >85% precision
- **Falsos negativos**: Reducir en 40%
- **Latencia**: <300ms promedio
- **Costo**: <$1/mes con HF API (con caché 80%)

### Queries de Prueba Críticas
```python
TEST_QUERIES = [
    ("tengo goteras", "plomero"),
    ("cortocircuito", "electricista"),
    ("necesito redecorar", "diseñador de interiores"),
    ("mi perro está enfermo", "veterinario"),
    ("quiero una app", "desarrollador web")
]
```

---

## Costos Estimados

### Hugging Face Inference API
- **Gratis**: ~1000 queries/día
- **Paid**: $0.0001/segundo de inferencia
- **Estimado**: $0.30/mes para 30,000 queries (sin caché)
- **Con 80% caché**: ~$0.06/mes

### Hugging Face Jobs (opcional)
- Solo necesario para regenerar embeddings periódicamente
- T4 small: ~$0.20/hora
- Una vez: ~10 min = ~$0.03

### Conclusión: Muy rentable

---

## Riesgos y Mitigación

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| HF API downtime | Media | Alto | Fallback a modelo local |
| Latencia alta | Baja | Medio | Redis caché de embeddings |
| Embeddings de mala calidad | Baja | Alto | Quality checks antes de rollout |
| pgvector lento | Baja | Medio | Índice HNSW + tuning |

---

## Futuro (Phase 2+)

### Month 2: Cross-encoder reranking
- Two-stage: retrieval (bi-encoder) + reranking (cross-encoder)
- +10-15% precision

### Month 3-4: Fine-tuning
- Recopilar 1000+ interacciones exitosas
- Crear dataset en Hugging Face Hub
- Fine-tune sentence-transformers con datos ecuatorianos
- +20% recall

### Month 5+: Multimodal
- Incorporar fotos de trabajos
- CLIP embeddings para imágenes

---

## Resumen de Implementación

**Tiempo total**: 10-12 días (1-2 semanas)

**Día 1-2**: Setup DB (pgvector, tablas, migración)
**Día 3-4**: Generar embeddings para proveedores existentes
**Día 5-6**: Implementar EmbeddingService
**Día 7-8**: Implementar búsqueda semántica
**Día 9-10**: Integración con ai-clientes
**Día 11-12**: Testing, deployment, monitoreo

**Recurso humano**: 1 developer full-time

**Stack técnico**:
- sentence-transformers (ML)
- pgvector (DB)
- Hugging Face (infrastructure)
- Docker (deployment)

---

## Siguientes Pasos Inmediatos

1. ✅ Verificar que pgvector está disponible en Supabase
2. ✅ Instalar dependencias (sentence-transformers)
3. ✅ Crear tabla de embeddings
4. ✅ Generar embeddings para 5-10 proveedores de prueba
5. ✅ Implementar `EmbeddingService`
6. ✅ Testear búsqueda semántica manualmente
7. ✅ Deployment a staging
8. ✅ A/B testing gradual

**¿Listo para comenzar?**
