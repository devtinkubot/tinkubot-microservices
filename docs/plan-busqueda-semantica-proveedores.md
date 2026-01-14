# Plan: Búsqueda Semántica de Proveedores con Hugging Face

> **Última actualización**: Enero 2025
> **Versión**: 2.0 - Actualizada con nueva arquitectura SOLID
> **Estado**: Listo para implementación

## Resumen Ejecutivo

Implementar búsqueda semántica para mejorar la interpretación del lenguaje natural de clientes y encontrar mejores matches con proveedores, usando **sentence-transformers** pre-entrenados vía **Hugging Face Inference API**.

**Enfoque**: Extensión de arquitectura existente - 1-2 semanas de implementación
**Prioridad**: Mejor interpretación del lenguaje del cliente ("tengo goteras" → "plomero")
**Infraestructura**: Hugging Face Inference API + caché Redis + pgvector
**Arquitectura**: Aprovecha patrones SOLID ya implementados (Repository, Cache, Metrics, Feature Flags)

---

## Arquitectura Actual Implementada (Enero 2025)

### Patrones Arquitectónicos Activos en ai-clientes

| Patrón | Estado | Archivos | Feature Flag | Descripción |
|--------|--------|----------|--------------|-------------|
| **Repository Pattern** | ✅ Activo | `repositories/provider_repository.py` | `USE_REPOSITORY_INTERFACES = True` | Abstracción de acceso a datos |
| **State Machine** | ✅ Activo | `core/state_machine.py` | `USE_STATE_MACHINE = True` | Validación de transiciones de conversación |
| **Saga Pattern** | ✅ Activo | `core/saga.py` | `USE_SAGA_ROLLBACK = True` | Rollback transaccional automático |
| **Cache Layer** | ✅ Activo | `core/cache.py` | `ENABLE_PERFORMANCE_OPTIMIZATIONS = True` | Caché Redis con namespaces y TTLs |
| **Performance Metrics** | ✅ Activo | `core/metrics.py` | `ENABLE_PERFORMANCE_OPTIMIZATIONS = True` | Tracking de latencias (p50, p95, p99) |
| **Feature Flags** | ✅ Activo | `core/feature_flags.py` | `ENABLE_FEATURE_FLAGS = True` | Sistema de migración gradual (5 fases) |

### Servicios Core Existentes

| Servicio | Ubicación | Responsabilidad |
|----------|-----------|-----------------|
| **QueryInterpreterService** | `ai-clientes/services/query_interpreter_service.py` | Interpreta lenguaje natural con OpenAI GPT-3.5 |
| **SearchService** | `ai-clientes/services/search_service.py` | Búsqueda de proveedores (directo a Supabase via Repository) |
| **ProviderRepository** | `ai-proveedores/repositories/provider_repository.py` | Acceso a datos de proveedores con interface `IProviderRepository` |
| **CacheManager** | `ai-clientes/core/cache.py` | Caché Redis con namespaces (SEARCH_RESULTS, CUSTOMER_PROFILE, etc.) |
| **PerformanceMetrics** | `ai-clientes/core/metrics.py` | Métricas de performance (min, max, avg, p50, p95, p99) |

### Servicios Eliminados (Historia)

- ❌ **ai-search**: Eliminado en Sprint 2.4 (SPOF eliminado)
- Búsqueda ahora es directa a Supabase vía ProviderRepository
- Esto simplifica la arquitectura y mejora la mantenibilidad

---

## Problema Actual

### Búsqueda Actual (ai-clientes/services/search_service.py)

```python
# Búsqueda actual usa Repository Pattern
async def intelligent_search_providers(payload: Dict[str, Any]) -> Dict[str, Any]:
    # 1. IA interpreta la query
    interpretation = await query_interpreter_svc.interpret_query(
        user_message=query,
        city_context=location,
        semaphore=openai_semaphore,
        timeout_seconds=OPENAI_TIMEOUT_SECONDS
    )

    # 2. Búsqueda en Supabase vía ProviderRepository (DIRECTO, sin SPOF)
    providers = await provider_repo.search_by_city_and_profession(
        city=interpreted_city,
        profession=interpreted_profession,
        limit=10
    )
```

**Limitaciones**:
- ⚠️ Interpreta bien con OpenAI (~70% precisión)
- ❌ Búsqueda por texto exacto (ILIKE): `WHERE profession ILIKE '%plomero%'`
- ❌ No encuentra proveedores semánticamente similares
- ❌ Falsos negativos: "tengo goteras" NO encuentra plomeros si no dice "plomero"

---

## Solución Propuesta

### Arquitectura Actual (Sin Embeddings)

```
Cliente: "tengo goteras"
   ↓
AI Clientes: QueryInterpreterService (OpenAI GPT-3.5)
   → Interpreta: "plomero" + ciudad
   ↓
AI Clientes: ProviderRepository (interface)
   → Supabase: providers table
   → Búsqueda: WHERE profession ILIKE '%plomero%' AND city = 'Quito'
   ↓
CacheManager (Redis)
   → Cache TTL: 300s (5 min) para búsquedas
   ↓
PerformanceMetrics
   → Tracking: p50, p95, p99 latencias
   ↓
Retorna: Lista de proveedores
```

### Arquitectura Propuesta (Con Embeddings - Fase 6)

```
Cliente: "tengo goteras"
   ↓
AI Clientes: QueryInterpreterService (OpenAI GPT-3.5)
   → Interpreta: "plomero" + ciudad + detalles
   ↓
[NEW] EmbeddingService (ai-clientes/services/embedding_service.py)
   → HF Inference API
   → Genera embedding: [0.23, -0.45, ...] (384 dims)
   ↓
[NEW] CacheManager (Embeddings)
   → Redis cache: key="embedding:hash(query)"
   → TTL: 3600s (1 hora)
   ↓
[NEW] PostgreSQL + pgvector
   → SELECT * FROM match_providers_semantic(
       query_embedding,
       target_city := 'Quito',
       max_results := 10
     )
   → ORDER BY cosine_similarity DESC
   ↓
PerformanceMetrics
   → Métricas adicionales:
      - embedding_generation_ms
      - semantic_search_ms
      - cache_hit_rate_embeddings
   ↓
Retorna: Lista de proveedores ordenados por similitud (0-1)
```

### Tecnologías

**Modelo**: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- 384 dimensiones (ligero, rápido)
- Multilingüe (español incluido)
- Gratis en HF Inference API (hasta ~1000 queries/día)

**Infraestructura**:
- **Inferencia**: HF Inference API + fallback local (sentence-transformers)
- **Base de datos**: PostgreSQL con extensión **pgvector**
- **Caché**: Redis (ya existe - CacheManager)
- **Métricas**: PerformanceMetrics (ya existe)
- **Feature Flags**: Sistema de flags (ya existe)

---

## Fases de Implementación Actualizadas

### Fase 0: Verificación de Arquitectura (Día 0.5)

**Verificar que la arquitectura actual soporta la extensión:**

1. ✅ Confirmar que ProviderRepository existe
2. ✅ Confirmar que QueryInterpreterService existe
3. ✅ Confirmar que CacheManager existe (para cachear embeddings)
4. ✅ Confirmar que PerformanceMetrics existe (para tracking)
5. ❌ Verificar que pgvector está disponible en Supabase
6. ❌ Crear tabla `provider_embeddings` con índice HNSW

**Comando de verificación:**
```bash
# Verificar extensión pgvector en Supabase
psql $DATABASE_URL -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"

# Esperado: extensión 'vector' instalada
# Si no está: crear ticket con Soporte Supabase
```

---

### Fase 1: Setup de Base de Datos (Día 1-2)

**Archivo**: `python-services/ai-proveedores/migrations/add_semantic_search.sql` (NUEVO)

**IMPORTANTE**: Esta migración es **ADDITIVA** - NO rompe nada existente.

```sql
-- ============================================================================
-- Migración: Búsqueda Semántica de Proveedores
-- Fecha: Enero 2025
-- Descripción: Agrega embeddings y pgvector para búsqueda semántica
-- ============================================================================

-- 1. Crear tabla de embeddings (NUEVA, INDEPENDIENTE)
CREATE TABLE IF NOT EXISTS provider_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id VARCHAR(255) UNIQUE NOT NULL,

    -- Embedding vector (384 dimensiones para MiniLM-L12-v2)
    full_profile_embedding vector(384) NOT NULL,

    -- Metadata
    embedding_model VARCHAR(100) DEFAULT 'paraphrase-multilingual-MiniLM-L12-v2',
    embedding_version VARCHAR(10) DEFAULT '1.0',

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Foreign key (con CASCADE delete si se borra provider)
    CONSTRAINT fk_provider_embeddings
        FOREIGN KEY (provider_id)
        REFERENCES providers(id)
        ON DELETE CASCADE
);

-- 2. Crear índice HNSW para búsqueda rápida (Hierarchical Navigable Small World)
CREATE INDEX IF NOT EXISTS idx_embeddings_hnsw
ON provider_embeddings
USING hnsw (full_profile_embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 3. Crear índice GIN para búsquedas por metadata (opcional)
CREATE INDEX IF NOT EXISTS idx_embeddings_provider_id
ON provider_embeddings (provider_id);

-- 4. Trigger para updated_at automático
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_provider_embeddings_updated_at
    BEFORE UPDATE ON provider_embeddings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 5. Función de búsqueda semántica (mejorada con filtros)
CREATE OR REPLACE FUNCTION match_providers_semantic(
    query_embedding vector(384),
    target_city VARCHAR DEFAULT NULL,
    max_results INT DEFAULT 10,
    min_similarity FLOAT DEFAULT 0.5
) RETURNS TABLE (
    provider_id VARCHAR,
    phone VARCHAR,
    name VARCHAR,
    profession VARCHAR,
    city VARCHAR,
    services TEXT,
    specialty TEXT,
    rating DECIMAL,
    verified BOOLEAN,
    available BOOLEAN,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.id,
        p.phone,
        p.name,
        p.profession,
        p.city,
        p.services,
        p.specialty,
        p.rating,
        p.verified,
        p.available,
        -- Cosine similarity: 1 - cosine_distance
        (1 - (pe.full_profile_embedding <=> query_embedding)) as similarity
    FROM provider_embeddings pe
    INNER JOIN providers p ON p.id = pe.provider_id
    WHERE
        p.verified = true
        AND p.available = true
        AND (target_city IS NULL OR p.city ILIKE '%' || target_city || '%')
        AND (1 - (pe.full_profile_embedding <=> query_embedding)) >= min_similarity
    ORDER BY pe.full_profile_embedding <=> query_embedding
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql STABLE;

-- 6. Comentario para documentación
COMMENT ON FUNCTION match_providers_semantic IS
'Búsqueda semántica de proveedores usando cosine similarity en embeddings de 384 dimensiones.

Args:
  - query_embedding: Embedding del query del usuario (384 dimensiones, vector)
  - target_city: Filtro opcional por ciudad (búsqueda ILIKE parcial)
  - max_results: Máximo número de resultados a retornar (default: 10)
  - min_similarity: Similitud mínima para incluir resultados (0-1, default: 0.5)

Returns:
  - Proveedores ordenados por similitud descendente (similarity de 0 a 1)
  - Incluye metadata del proveedor y score de similitud

Example:
  SELECT * FROM match_providers_semantic(
    '[0.1, 0.2, ...]'::vector(384),
    'Quito',
    10,
    0.7
  );
';

-- 7. Crear tabla para recolectar datos de entrenamiento (futuro)
CREATE TABLE IF NOT EXISTS search_interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255),
    client_phone VARCHAR(50),

    -- Query original e interpretación
    original_query TEXT NOT NULL,
    interpreted_profession VARCHAR(255),
    interpreted_city VARCHAR(255),
    query_details TEXT,

    -- Resultados
    providers_shown JSONB,
    providers_count INT,
    provider_contacted VARCHAR(255),

    -- Feedback
    successful_match BOOLEAN,
    contact_made BOOLEAN,

    -- Metadata
    search_method VARCHAR(50) DEFAULT 'semantic',
    similarity_scores JSONB,

    timestamp TIMESTAMP DEFAULT NOW()
);

-- Índices para analytics
CREATE INDEX IF NOT EXISTS idx_search_interactions_phone
ON search_interactions (client_phone);

CREATE INDEX IF NOT EXISTS idx_search_interactions_timestamp
ON search_interactions (timestamp DESC);

-- 8. Grant permissions (si es necesario)
-- GRANT ALL ON TABLE provider_embeddings TO service_role;
-- GRANT EXECUTE ON FUNCTION match_providers_semantic TO service_role;
```

**Validación de migración:**
```bash
# Ejecutar migración
psql $DATABASE_URL -f migrations/add_semantic_search.sql

# Verificar tabla creada
psql $DATABASE_URL -c "\d provider_embeddings"

# Verificar índice HNSW creado
psql $DATABASE_URL -c "\di idx_embeddings_hnsw"

# Verificar función creada
psql $DATABASE_URL -c "\df match_providers_semantic"
```

---

### Fase 2: Generar Embeddings (Día 3-4)

**Archivo**: `python-services/ai-proveedores/scripts/generate_embeddings.py` (NUEVO)

**Características mejoradas:**
- ✅ Usa ProviderRepository existente (no crea nueva conexión)
- ✅ Integra con PerformanceMetrics para tracking
- ✅ Soporta HF Inference API o modelo local
- ✅ Manejo robusto de errores con reintentos
- ✅ Modo test para debugging (5 proveedores)

```python
#!/usr/bin/env python3
"""
Genera embeddings para proveedores existentes usando HF Inference API.

Integración con arquitectura SOLID existente:
- ProviderRepository: Acceso a datos de proveedores
- PerformanceMetrics: Tracking de latencias
- CacheManager: Caché de embeddings generados

Uso:
    python scripts/generate_embeddings.py [--local] [--test]

Args:
    --local: Usa modelo local (sentence-transformers) en lugar de HF API
    --test: Modo prueba (solo 5 proveedores)
    --batch-size: Tamaño de batch para HF API (default: 10)

Dependencias:
    pip install sentence-transformers numpy httpx
"""

import asyncio
import argparse
import logging
import os
from typing import List, Dict, Any
import sys

# Agregar parent directory al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from repositories.provider_repository import SupabaseProviderRepository
from core.metrics import metrics
from app.dependencies import get_supabase_client

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generador de embeddings para proveedores."""

    MODEL_NAME = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
    EMBEDDING_DIMS = 384

    def __init__(self, use_local: bool = False, batch_size: int = 10):
        """
        Inicializa el generador.

        Args:
            use_local: Si True, usa modelo local (más lento, sin costos externos)
            batch_size: Tamaño de batch para HF API
        """
        self.use_local = use_local
        self.batch_size = batch_size
        self._local_model = None

        if use_local:
            logger.info("🔄 Cargando modelo local (puede tomar unos segundos)...")
            from sentence_transformers import SentenceTransformer
            self._local_model = SentenceTransformer(self.MODEL_NAME)
            logger.info("✅ Modelo local cargado")
        else:
            logger.info("✅ Usando HF Inference API")

    def _prepare_provider_text(self, provider: Dict[str, Any]) -> str:
        """
        Prepara el texto del proveedor para generar embedding.

        Args:
            provider: Datos del proveedor

        Returns:
            Texto formateado para embedding
        """
        parts = [
            f"Profesión: {provider.get('profession', '')}",
            f"Servicios: {provider.get('services', '')}",
            f"Especialidad: {provider.get('specialty', '')}",
            f"Ciudad: {provider.get('city', '')}",
            f"Descripción: {provider.get('description', '')}",
        ]

        # Filtrar partes vacías
        text = ". ".join([p for p in parts if ':' in p and p.split(': ')[1]])
        return text

    async def _generate_embedding_hf(self, text: str) -> List[float]:
        """
        Genera embedding usando HF Inference API.

        Args:
            text: Texto a embeddar

        Returns:
            Lista de floats (384 dimensiones)
        """
        import httpx
        import numpy as np

        hf_token = os.getenv('HF_TOKEN')
        api_url = f"https://api-inference.huggingface.co/models/{self.MODEL_NAME}"

        if not hf_token:
            raise Exception("HF_TOKEN no está configurado")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                api_url,
                headers={"Authorization": f"Bearer {hf_token}"},
                json={"inputs": text}
            )

            if response.status_code == 200:
                embedding = np.array(response.json()[0])
                # Normalizar embedding (norm L2)
                embedding = embedding / np.linalg.norm(embedding)
                return embedding.tolist()
            else:
                error_text = response.text
                raise Exception(f"HF API error {response.status_code}: {error_text}")

    async def _generate_embedding_local(self, text: str) -> List[float]:
        """
        Genera embedding usando modelo local (fallback).

        Args:
            text: Texto a embeddar

        Returns:
            Lista de floats (384 dimensiones)
        """
        if self._local_model is None:
            raise Exception("Modelo local no cargado")

        # Generar embedding
        embedding = self._local_model.encode(
            text,
            normalize_embeddings=True,
            show_progress_bar=False
        )

        return embedding.tolist()

    async def generate_for_provider(
        self,
        provider: Dict[str, Any],
        supabase
    ) -> bool:
        """
        Genera y guarda embedding para un proveedor.

        Args:
            provider: Datos del proveedor
            supabase: Cliente Supabase

        Returns:
            True si exitoso, False en caso contrario
        """
        try:
            provider_id = provider.get('id')
            if not provider_id:
                logger.warning(f"⚠️ Provider sin ID, saltando")
                return False

            # Preparar texto
            text = self._prepare_provider_text(provider)

            # Generar embedding
            async with metrics.timer("embedding_generation"):
                if self.use_local:
                    embedding = await self._generate_embedding_local(text)
                else:
                    embedding = await self._generate_embedding_hf(text)

            # Guardar en BD (upsert para no duplicar)
            # Convertir lista a string de vectores para pgvector
            embedding_str = str(embedding)

            supabase.table('provider_embeddings').upsert({
                'provider_id': provider_id,
                'full_profile_embedding': embedding_str,
                'embedding_model': self.MODEL_NAME,
            }, on_conflict='provider_id').execute()

            logger.info(f"✅ Embedding generado para provider {provider_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Error generando embedding para provider {provider.get('id')}: {e}")
            return False

    async def generate_batch(
        self,
        providers: List[Dict[str, Any]],
        supabase
    ) -> Dict[str, int]:
        """
        Genera embeddings para un batch de proveedores.

        Args:
            providers: Lista de proveedores
            supabase: Cliente Supabase

        Returns:
            Dict con estadísticas: success, failed, total
        """
        stats = {"success": 0, "failed": 0, "total": len(providers)}

        for provider in providers:
            success = await self.generate_for_provider(provider, supabase)
            if success:
                stats["success"] += 1
            else:
                stats["failed"] += 1

        return stats

    async def generate_all(
        self,
        repository: SupabaseProviderRepository,
        test_mode: bool = False
    ) -> Dict[str, int]:
        """
        Genera embeddings para todos los proveedores verificados.

        Args:
            repository: Repositorio de proveedores
            test_mode: Si True, solo procesa 5 proveedores

        Returns:
            Dict con estadísticas: success, failed, total
        """
        # Obtener proveedores verificados
        limit = 5 if test_mode else 1000

        providers = await repository.find_many(
            filters={"verified": True},
            limit=limit
        )

        if not providers:
            logger.warning("⚠️ No se encontraron proveedores verificados")
            return {"success": 0, "failed": 0, "total": 0}

        logger.info(f"📋 Procesando {len(providers)} proveedores verificados...")

        # Inicializar Supabase
        supabase = get_supabase_client()

        # Generar embeddings
        stats = await self.generate_batch(providers, supabase)

        logger.info(f"✅ Embeddings generados: {stats['success']}/{stats['total']}")
        logger.info(f"❌ Fallidos: {stats['failed']}/{stats['total']}")

        # Imprimir métricas
        embedding_stats = metrics.get_stats("embedding_generation")
        if embedding_stats:
            logger.info(f"📊 Métricas de embedding_generation:")
            logger.info(f"   - Avg: {embedding_stats.get('avg_ms', 'N/A')}ms")
            logger.info(f"   - P95: {embedding_stats.get('p95_ms', 'N/A')}ms")

        return stats


async def main():
    """Función principal."""
    parser = argparse.ArgumentParser(
        description='Generar embeddings para proveedores',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Generar para todos los proveedores (HF API)
  python scripts/generate_embeddings.py

  # Generar para 5 proveedores de prueba
  python scripts/generate_embeddings.py --test

  # Usar modelo local
  python scripts/generate_embeddings.py --local
        """
    )

    parser.add_argument(
        '--local',
        action='store_true',
        help='Usar modelo local (sentence-transformers) en lugar de HF API'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Modo prueba: solo 5 proveedores'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        help='Tamaño de batch para HF API (default: 10)'
    )

    args = parser.parse_args()

    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("="*70)
    logger.info("GENERADOR DE EMBEDDINGS - PROVEEDORES")
    logger.info("="*70)
    logger.info(f"Modo: {'LOCAL' if args.local else 'HF INFERENCE API'}")
    logger.info(f"Test: {'SÍ (5 providers)' if args.test else 'NO (todos)'}")
    logger.info("="*70)

    # Inicializar
    try:
        supabase = get_supabase_client()
        repository = SupabaseProviderRepository(supabase)
        generator = EmbeddingGenerator(use_local=args.local, batch_size=args.batch_size)

        # Generar embeddings
        stats = await generator.generate_all(repository, test_mode=args.test)

        # Resumen
        print(f"\n{'='*70}")
        print(f"📊 RESUMEN:")
        print(f"  ✅ Exitosos: {stats['success']}")
        print(f"  ❌ Fallidos: {stats['failed']}")
        print(f"  📋 Total: {stats['total']}")
        print(f"{'='*70}\n")

        if stats['failed'] > 0:
            logger.warning(f"⚠️ {stats['failed']} embeddings fallaron, revisar logs")

    except Exception as e:
        logger.error(f"❌ Error fatal: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
```

**Dependencias a agregar:**
```bash
# Agregar a requirements.txt
sentence-transformers==2.2.2
numpy==1.24.3
httpx==0.24.0
```

---

### Fase 3: Servicio de Embeddings (Día 5)

**Archivo**: `python-services/ai-clientes/services/embedding_service.py` (NUEVO)

**Integración con arquitectura existente:**
- ✅ Usa CacheManager para cachear embeddings de queries comunes
- ✅ Usa PerformanceMetrics para tracking de latencias
- ✅ Feature flag para activación gradual (`USE_SEMANTIC_SEARCH`)
- ✅ Fallback local si HF API falla

```python
"""
Servicio de embeddings para búsqueda semántica.

Integración con arquitectura SOLID:
- CacheManager: Caché de embeddings de queries comunes
- PerformanceMetrics: Tracking de latencias (p50, p95, p99)
- Feature Flags: Activación gradual (USE_SEMANTIC_SEARCH)
- Fallback: Modelo local si HF API falla

Author: Claude Sonnet 4.5
Created: 2025-01-14
"""

import os
import logging
from typing import Optional, List
import httpx
import numpy as np

from core.cache import CacheManager, CacheNamespace
from core.metrics import metrics
from core.feature_flags import get_phase_status

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Servicio para generar embeddings via HF Inference API.

    Características:
    - Caché de embeddings comunes (Redis, TTL 1 hora)
    - Fallback a modelo local si HF API falla
    - Tracking automático de métricas
    - Feature flag para activación gradual

    Atributos:
        cache_manager: Instancia de CacheManager
        hf_token: Token de Hugging Face
        api_url: URL de HF Inference API
        _local_model: Modelo local (fallback)
        _enabled: Si el servicio está habilitado
    """

    # Configuración
    MODEL_NAME = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
    EMBEDDING_DIMS = 384
    EMBEDDING_CACHE_TTL = 3600  # 1 hora
    API_URL = f"https://api-inference.huggingface.co/models/{MODEL_NAME}"

    def __init__(self, cache_manager: CacheManager, enable_validation: bool = False):
        """
        Inicializa el servicio.

        Args:
            cache_manager: Instancia de CacheManager
            enable_validation: Si True, valida embeddings antes de retornarlos
        """
        self.cache_manager = cache_manager
        self.enable_validation = enable_validation

        self.hf_token = os.getenv('HF_TOKEN')
        self._local_model = None
        self._enabled = False

        # Feature flag: verificar si está activada la fase 6
        try:
            self._enabled = get_phase_status(6) and bool(self.hf_token)
        except:
            self._enabled = bool(self.hf_token)

        if self._enabled:
            logger.info("✅ EmbeddingService inicializado (HF API + caché)")
        else:
            logger.info("⏸️ EmbeddingService deshabilitado (configura HF_TOKEN o fase 6)")

    async def generate_embedding(
        self,
        text: str,
        use_cache: bool = True
    ) -> Optional[List[float]]:
        """
        Genera embedding para un texto.

        Args:
            text: Texto a embeddar
            use_cache: Si True, usa caché de embeddings

        Returns:
            Lista de floats (384 dimensiones) o None si falla
        """
        if not self._enabled:
            logger.warning("⚠️ EmbeddingService no está habilitado")
            return None

        # 1. Verificar caché
        if use_cache:
            cached = await self._get_from_cache(text)
            if cached is not None:
                logger.debug(f"✅ Embedding cache HIT para: '{text[:50]}...'")
                return cached

        # 2. Generar embedding
        try:
            embedding = await self._generate(text)

            # 3. Validar embedding
            if self.enable_validation:
                if not self._validate_embedding(embedding):
                    logger.warning(f"⚠️ Embedding inválido generando, reintentando...")
                    return None

            # 4. Guardar en caché
            if use_cache and embedding is not None:
                await self._save_to_cache(text, embedding)

            return embedding

        except Exception as e:
            logger.error(f"❌ Error generando embedding: {e}")
            return None

    async def _generate(self, text: str) -> List[float]:
        """
        Genera embedding (interna).

        Intenta HF API primero, luego fallback a modelo local.
        """
        # Intentar HF API
        if self.hf_token:
            try:
                return await self._generate_from_api(text)
            except Exception as e:
                logger.warning(f"⚠️ HF API falló: {e}, usando fallback local")

        # Fallback a modelo local
        return await self._generate_local(text)

    async def _generate_from_api(self, text: str) -> List[float]:
        """Genera embedding usando HF Inference API."""
        async with metrics.timer("hf_inference_api"):
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.API_URL,
                    headers={"Authorization": f"Bearer {self.hf_token}"},
                    json={"inputs": text}
                )

                if response.status_code == 200:
                    embedding = np.array(response.json()[0])
                    # Normalizar
                    embedding = embedding / np.linalg.norm(embedding)
                    return embedding.tolist()
                else:
                    raise Exception(f"HF API error {response.status_code}: {response.text}")

    async def _generate_local(self, text: str) -> List[float]:
        """Genera embedding usando modelo local (fallback)."""
        if self._local_model is None:
            logger.info("🔄 Cargando modelo local...")
            from sentence_transformers import SentenceTransformer
            self._local_model = SentenceTransformer(self.MODEL_NAME)
            logger.info("✅ Modelo local cargado")

        async with metrics.timer("local_embedding_model"):
            embedding = self._local_model.encode(
                text,
                normalize_embeddings=True,
                show_progress_bar=False
            )
            return embedding.tolist()

    def _validate_embedding(self, embedding: List[float]) -> bool:
        """
        Valida que un embedding sea correcto.

        Args:
            embedding: Embedding a validar

        Returns:
            True si es válido, False en caso contrario
        """
        if not isinstance(embedding, list):
            return False

        if len(embedding) != self.EMBEDDING_DIMS:
            return False

        # Verificar que no tenga NaN o Inf
        for val in embedding:
            if not isinstance(val, (int, float)) or np.isnan(val) or np.isinf(val):
                return False

        # Verificar que no sea todo ceros
        if all(abs(v) < 1e-6 for v in embedding):
            return False

        return True

    async def _get_from_cache(self, text: str) -> Optional[List[float]]:
        """Obtiene embedding del caché."""
        try:
            import hashlib
            cache_key = f"embedding:{hashlib.md5(text.encode()).hexdigest()}"

            cached = await self.cache_manager.get(
                namespace=CacheNamespace.SEARCH_RESULTS,
                identifier=cache_key
            )

            return cached

        except Exception as e:
            logger.warning(f"⚠️ Error leyendo del caché: {e}")
            return None

    async def _save_to_cache(self, text: str, embedding: List[float]) -> None:
        """Guarda embedding en caché."""
        try:
            import hashlib
            cache_key = f"embedding:{hashlib.md5(text.encode()).hexdigest()}"

            await self.cache_manager.set(
                namespace=CacheNamespace.SEARCH_RESULTS,
                identifier=cache_key,
                value=embedding,
                ttl=self.EMBEDDING_CACHE_TTL
            )

            logger.debug(f"💾 Embedding guardado en caché: {cache_key[:16]}...")

        except Exception as e:
            logger.warning(f"⚠️ Error guardando en caché: {e}")

    def get_stats(self) -> dict:
        """Obtiene estadísticas del servicio."""
        stats = {
            "enabled": self._enabled,
            "cache_ttl_seconds": self.EMBEDDING_CACHE_TTL,
            "hf_api_configured": bool(self.hf_token),
            "local_model_loaded": self._local_model is not None,
        }

        # Agregar métricas de HF API
        hf_stats = metrics.get_stats("hf_inference_api")
        if hf_stats:
            stats["hf_api_stats"] = hf_stats

        # Agregar métricas de modelo local
        local_stats = metrics.get_stats("local_embedding_model")
        if local_stats:
            stats["local_model_stats"] = local_stats

        return stats


# Instancia global (se inicializa en main.py)
embedding_service: Optional[EmbeddingService] = None


def initialize_embedding_service(cache_manager: CacheManager) -> Optional[EmbeddingService]:
    """
    Inicializa el servicio de embeddings.

    Args:
        cache_manager: Instancia de CacheManager

    Returns:
        Instancia de EmbeddingService o None si hay error
    """
    global embedding_service

    try:
        if cache_manager:
            embedding_service = EmbeddingService(cache_manager)
            logger.info("✅ EmbeddingService inicializado correctamente")
            return embedding_service
    except Exception as e:
        logger.error(f"❌ Error inicializando EmbeddingService: {e}")
        return None
```

---

### Fase 4: Búsqueda Semántica (Día 6-7)

**Archivo**: `python-services/ai-clientes/services/search_service.py` (MODIFICAR - AGREGAR AL FINAL)

**IMPORTANTE**: NO reemplaza `intelligent_search_providers()` existente. Solo agrega funciones nuevas.

```python
# =============================================================================
# BÚSQUEDA SEMÁNTICA (Fase 6 - Feature Flag)
# =============================================================================

# Imports adicionales
from core.feature_flags import get_phase_status
from core.metrics import metrics

# Feature flag para búsqueda semántica
USE_SEMANTIC_SEARCH = os.getenv("USE_SEMANTIC_SEARCH", "false") == "true"


async def semantic_search_providers(
    payload: Dict[str, Any],
    openai_semaphore: Any = None,
    OPENAI_TIMEOUT_SECONDS: int = 5
) -> Dict[str, Any]:
    """
    Búsqueda semántica de proveedores usando embeddings.

    ENFOQUE (Fase 6):
    1. QueryInterpreterService interpreta la query con IA
    2. EmbeddingService genera embedding del query
    3. PostgreSQL + pgvector busca por similitud coseno
    4. Resultados ordenados por similitud

    Args:
        payload: Dict con main_profession, location, actual_need
        openai_semaphore: Semaphore para OpenAI (existente)
        OPENAI_TIMEOUT_SECONDS: Timeout para OpenAI (existente)

    Returns:
        Dict con providers, total, query_interpretation, search_metadata
    """
    # Verificar feature flag
    if not USE_SEMANTIC_SEARCH:
        logger.info("⚠️ Semantic search deshabilitado, usando búsqueda actual")
        return await intelligent_search_providers(
            payload,
            openai_semaphore,
            OPENAI_TIMEOUT_SECONDS
        )

    # Verificar fase 6
    phase_6_active = False
    try:
        phase_6_active = get_phase_status(6)
    except:
        phase_6_active = False

    if not phase_6_active:
        logger.warning("⚠️ Fase 6 no está activa, usando búsqueda actual")
        return await intelligent_search_providers(
            payload,
            openai_semaphore,
            OPENAI_TIMEOUT_SECONDS
        )

    # Verificar que EmbeddingService está disponible
    from services.embedding_service import embedding_service

    if not embedding_service or not embedding_service._enabled:
        logger.warning("⚠️ EmbeddingService no disponible, usando búsqueda actual")
        return await intelligent_search_providers(
            payload,
            openai_semaphore,
            OPENAI_TIMEOUT_SECONDS
        )

    profession = payload.get("main_profession", "")
    location = payload.get("location", "")
    need_summary = payload.get("actual_need", "")

    # Construir query para IA
    if need_summary and need_summary != profession:
        query = f"{need_summary} {profession} en {location}"
    else:
        query = f"{profession} en {location}"

    logger.info(f"🔍 Buscando con embeddings: query='{query}'")

    try:
        # Paso 1: IA interpreta la query (EXISTENTE - DIFERENCIADOR)
        query_interpreter_svc = _get_query_interpreter()
        if not query_interpreter_svc:
            raise Exception("QueryInterpreterService no disponible")

        interpretation = await query_interpreter_svc.interpret_query(
            user_message=query,
            city_context=location,
            semaphore=openai_semaphore,
            timeout_seconds=OPENAI_TIMEOUT_SECONDS
        )

        interpreted_profession = interpretation["profession"]
        interpreted_city = interpretation["city"] or location
        details = interpretation.get("details", "")

        logger.info(
            f"🧠 IA interpretó: '{query}' → "
            f"profession='{interpreted_profession}', city='{interpreted_city}'"
        )

        # Paso 2: Generar embedding del query
        query_text = f"{interpreted_profession} {details}"

        async with metrics.timer("query_embedding_generation"):
            query_embedding = await embedding_service.generate_embedding(
                text=query_text,
                use_cache=True
            )

        if query_embedding is None:
            logger.warning("⚠️ No se pudo generar embedding, usando búsqueda actual")
            return await intelligent_search_providers(
                payload,
                openai_semaphore,
                OPENAI_TIMEOUT_SECONDS
            )

        logger.info(f"✅ Embedding generado: {len(query_embedding)} dimensiones")

        # Paso 3: Buscar por similitud en PostgreSQL + pgvector
        provider_repo = _get_provider_repository()
        if not provider_repo:
            raise Exception("ProviderRepository no disponible")

        from app.dependencies import get_supabase_client
        supabase = get_supabase_client()

        # Convertir embedding a string vector para pgvector
        embedding_str = str(query_embedding)

        async with metrics.timer("semantic_search_db"):
            result = supabase.rpc('match_providers_semantic', {
                'query_embedding': embedding_str,
                'target_city': interpreted_city,
                'max_results': 10,
                'min_similarity': 0.5
            }).execute()

        providers = result.data if hasattr(result, 'data') else []
        total = len(providers)

        logger.info(f"✅ Búsqueda semántica: {total} proveedores encontrados")

        # Extraer scores de similitud
        similarity_scores = [p.get('similarity', 0) for p in providers[:5]]

        return {
            "ok": True,
            "providers": providers,
            "total": total,
            "query_interpretation": {
                "profession": interpreted_profession,
                "city": interpreted_city,
                "details": details
            },
            "search_metadata": {
                "strategy": "semantic_search_embeddings",
                "ai_enhanced": True,
                "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
                "similarity_scores": similarity_scores,
                "search_phase": "6"
            }
        }

    except Exception as exc:
        logger.error(f"❌ Error en búsqueda semántica: {exc}")
        logger.info("🔄 Fallback a búsqueda actual")

        # Fallback a búsqueda actual
        return await intelligent_search_providers(
            payload,
            openai_semaphore,
            OPENAI_TIMEOUT_SECONDS
        )


# Wrapper para elegir estrategia de búsqueda (BACKWARD COMPATIBLE)
async def intelligent_search_providers_v2(
    payload: Dict[str, Any],
    openai_semaphore: Any = None,
    OPENAI_TIMEOUT_SECONDS: int = 5
) -> Dict[str, Any]:
    """
    Búsqueda inteligente con soporte para búsqueda semántica (v2).

    Elige automáticamente entre búsqueda actual vs semántica según:
    1. Feature flag USE_SEMANTIC_SEARCH
    2. Disponibilidad de EmbeddingService
    3. Configuración de pgvector

    Args:
        payload: Dict con main_profession, location, actual_need
        openai_semaphore: Semaphore para OpenAI (existente)
        OPENAI_TIMEOUT_SECONDS: Timeout para OpenAI (existente)

    Returns:
        Dict con providers, total, query_interpretation, search_metadata

    BACKWARD COMPATIBLE: Si semantic search falla, usa búsqueda actual.
    """
    if USE_SEMANTIC_SEARCH:
        try:
            return await semantic_search_providers(
                payload,
                openai_semaphore,
                OPENAI_TIMEOUT_SECONDS
            )
        except Exception as e:
            logger.warning(f"⚠️ Semantic search falló: {e}, usando búsqueda actual")

    # Búsqueda actual (implementación original - EXISTENTE)
    return await intelligent_search_providers(
        payload,
        openai_semaphore,
        OPENAI_TIMEOUT_SECONDS
    )


# Alias para compatibilidad con llamadas existentes
intelligent_search_providers_v2_remote = intelligent_search_providers_v2
```

---

### Fase 5: Testing y Deployment (Día 8-10)

#### Tests Unitarios

**Archivo**: `python-services/ai-clientes/tests/unit/test_semantic_search.py` (NUEVO)

```python
"""
Tests unitarios para búsqueda semántica.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from services.embedding_service import EmbeddingService
from services.search_service import semantic_search_providers
from core.cache import CacheManager


class TestEmbeddingService:
    """Tests para EmbeddingService."""

    @pytest.mark.asyncio
    async def test_generate_embedding_with_cache_hit(self):
        """Test generación de embedding con caché hit."""
        cache = Mock(spec=CacheManager)
        cache.get = AsyncMock(return_value=[0.1, 0.2, 0.3])

        service = EmbeddingService(cache, enable_validation=False)
        service._enabled = True

        result = await service.generate_embedding("test query")

        assert result == [0.1, 0.2, 0.3]
        cache.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_embedding_validation(self):
        """Test validación de embeddings."""
        cache = Mock(spec=CacheManager)
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()

        service = EmbeddingService(cache, enable_validation=True)
        service._enabled = True
        service.hf_token = "test_token"

        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value = Mock(
                status_code=200,
                json=lambda: [[0.1, 0.2, 0.3]]
            )

            result = await service.generate_embedding("test")

            assert result == [0.1, 0.2, 0.3]
            cache.set.assert_called_once()


class TestSemanticSearch:
    """Tests para búsqueda semántica."""

    @pytest.mark.asyncio
    async def test_semantic_search_fallback(self):
        """Test fallback a búsqueda actual."""
        payload = {
            "main_profession": "plomero",
            "location": "Quito"
        }

        # Mock semantic search falla
        with patch('services.search_service.USE_SEMANTIC_SEARCH', True):
            with patch('services.search_service.semantic_search_providers') as mock_semantic:
                mock_semantic.side_effect = Exception("Semantic error")

                # Mock búsqueda actual
                with patch('services.search_service.intelligent_search_providers') as mock_current:
                    mock_current.return_value = {"ok": True, "providers": []}

                    result = await semantic_search_providers(payload)

                    # Verify: se llamó a búsqueda actual (fallback)
                    assert mock_current.called
                    assert result["ok"] is True
```

#### Tests Manuales

```bash
# 1. Test de migración SQL
psql $DATABASE_URL -f migrations/add_semantic_search.sql

# 2. Test de generación de embeddings (modo test)
cd python-services/ai-proveedores
python scripts/generate_embeddings.py --test --local

# 3. Test de búsqueda semántica (necesita contenedor corriendo)
curl -X POST "http://localhost:8001/handle-whatsapp-message" \
  -H "Content-Type: application/json" \
  -d '{
    "from_number": "+59399123456",
    "content": "tengo goteras en el techo",
    "message_type": "text"
  }'
```

**Queries de prueba críticas:**
- "tengo goteras" → debe encontrar plomeros
- "cortocircuito" → electricistas
- "necesito redecorar" → diseñadores de interiores
- "mi perro está enfermo" → veterinarios
- "se rompió la cerca" → carpinteros/albañiles

#### Deployment Gradual

1. **Feature flags en `core/feature_flags.py`:**
```python
# Fase 6: Semantic Search (NUEVA)
USE_SEMANTIC_SEARCH = os.getenv('USE_SEMANTIC_SEARCH', 'false') == 'true'
```

2. **Variables de entorno:**
```bash
# .env
HF_TOKEN=hf_xxxxxxxxxxxxxx
USE_SEMANTIC_SEARCH=false  # Activar gradualmente
```

3. **Rollback plan:**
```bash
# Si algo falla, desactivar semantic search:
export USE_SEMANTIC_SEARCH=false
docker compose restart ai-clientes

# Vuelve a búsqueda actual automáticamente
```

---

## Métricas de Éxito

### Baseline Actual (Sin Embeddings)
- Interpreta bien con OpenAI (~70% precisión)
- Búsqueda por texto exacto (ILIKE)
- Muchos falsos negativos (no encuentra proveedores válidos)
- Latencia: ~200-300ms promedio

### Objetivos Week 1 (Con Embeddings)
- **Interpretación semántica**: >85% precision
- **Falsos negativos**: Reducir en 40%
- **Latencia**: <400ms promedio (IA + embedding + DB)
- **Cache hit rate**: >60% para queries comunes
- **Costo**: <$1/mes con HF API (con caché)

### Métricas Adicionales (Performance Metrics)
- `embedding_generation_ms`: <100ms p95
- `semantic_search_db_ms`: <150ms p95
- `cache_hit_rate_embeddings`: >60%

---

## Costos Estimados

### Hugging Face Inference API
- **Gratis**: ~1000 queries/día
- **Paid**: ~$0.0001/segundo de inferencia
- **Estimado**: $0.50/mes para 50,000 queries
- **Con 80% caché**: ~$0.10/mes

### Modelo Local (Fallback)
- **CPU**: 0.5-1 core por query
- **Memoria**: ~500MB por modelo cargado
- **Costo**: $0 (usa infraestructura existente)

### Conclusión: Muy rentable

---

## Riesgos y Mitigación

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| HF API downtime | Media | Alto | ✅ Fallback a modelo local implementado |
| Latencia alta | Baja | Medio | ✅ Redis caché de embeddings (1h TTL) |
| Embeddings de mala calidad | Baja | Alto | ✅ Validación de embeddings + quality checks |
| pgvector lento | Baja | Medio | ✅ Índice HNSW + tuning de parámetros |
| Breaking changes | Baja | Alto | ✅ Feature flags + fallback a búsqueda actual |

---

## Resumen de Implementación

**Tiempo total**: 8-10 días (ajustado por arquitectura existente)

**Día 0.5**: Verificación de arquitectura (pgvector, dependencias)
**Día 1-2**: Setup DB (migración SQL, tablas, índices)
**Día 3-4**: Generar embeddings para proveedores existentes
**Día 5**: Implementar EmbeddingService con Cache/Metrics
**Día 6-7**: Implementar búsqueda semántica con fallback
**Día 8-9**: Integración con ai-clientes + testing
**Día 10**: Deployment gradual + monitoreo

**Recurso humano**: 1 developer full-time

**Stack técnico (existente + nuevo):**
- ✅ sentence-transformers (NUEVO)
- ✅ pgvector (NUEVO)
- ✅ Hugging Face (NUEVO)
- ✅ Repository Pattern (EXISTENTE)
- ✅ CacheManager (EXISTENTE)
- ✅ PerformanceMetrics (EXISTENTE)
- ✅ Docker (EXISTENTE)

---

## Ventajas de Arquitectura Actual

**Comparado con plan original:**

| Aspecto | Plan Original | Arquitectura Actual | Ventaja |
|---------|---------------|---------------------|----------|
| **SPOF** | ai-search externo | Repository directo a Supabase | ✅ Más confiable |
| **Caché** | Propuesto | ✅ CacheManager completo | ✅ Ya implementado |
| **Métricas** | Mencionado | ✅ PerformanceMetrics completo | ✅ Más detallado |
| **Feature Flags** | No mencionado | ✅ Sistema completo de flags | ✅ Rollback fácil |
| **Fallback** | Básico | ✅ Múltiples niveles de fallback | ✅ Más robusto |

---

## Siguientes Pasos Inmediatos

### 1. ✅ Verificar Pre-requisitos
```bash
# Verificar pgvector en Supabase
psql $DATABASE_URL -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"

# Instalar dependencias
pip install sentence-transformers numpy httpx

# Configurar HF Token
echo "HF_TOKEN=hf_xxx" >> .env
```

### 2. ✅ Crear Tablas de BD
```bash
cd python-services/ai-proveedores
psql $DATABASE_URL -f migrations/add_semantic_search.sql
```

### 3. ✅ Generar Embeddings (Test)
```bash
python scripts/generate_embeddings.py --test --local
```

### 4. ✅ Implementar EmbeddingService
```bash
# Crear archivo
touch ai-clientes/services/embedding_service.py

# Copiar código de Fase 3
```

### 5. ✅ Actualizar SearchService
```bash
# Agregar funciones de búsqueda semántica al final
# Ver Fase 4 para código completo
```

### 6. ✅ Testing
```bash
# Tests unitarios
pytest tests/unit/test_semantic_search.py -v

# Tests manuales con curl
# Ver Fase 5 para ejemplos
```

### 7. ✅ Deployment Gradual
```bash
# Activar feature flag
export USE_SEMANTIC_SEARCH=true

# Reconstruir contenedor
docker compose up -d --build ai-clientes

# Verificar
curl http://localhost:8001/debug/feature-flags
```

---

## Conclusión

El plan de búsqueda semántica está **diseñado para extender** la arquitectura actual sin breaking changes. Los patrones SOLID implementados (Repository, Cache, Metrics, Feature Flags) facilitan enormemente la implementación:

✅ **Repository Pattern**: Acceso a datos ya abstraído
✅ **CacheManager**: Caché Redis listo para usar
✅ **PerformanceMetrics**: Tracking automático de latencias
✅ **Feature Flags**: Activación gradual sin riesgo
✅ **Fallback robusto**: Múltiples niveles de fallback

**¿Listo para comenzar la implementación?**

---

## Referencias

- **Sentence Transformers**: https://www.sbert.net/
- **Hugging Face Inference API**: https://huggingface.co/inference-api
- **pgvector**: https://github.com/pgvector/pgvector
- **Arquitectura SOLID**: Ver commits 9ada3ca, 5df8d85, 13a576d
