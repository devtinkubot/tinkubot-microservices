"""
Servicio principal de búsqueda para Search Service
"""

import asyncio
import hashlib
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import asyncpg
from models.schemas import (
    Metrics,
    ProviderInfo,
    SearchFilters,
    SearchMetadata,
    SearchRequest,
    SearchResult,
    SearchStrategy,
)
from services.cache_service import cache_service
from utils.text_processor import TextProcessor, analyze_query

from shared_lib.config import settings

logger = logging.getLogger(__name__)


class SearchService:
    """Servicio de búsqueda optimizado con múltiples estrategias"""

    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.text_processor = TextProcessor()

    async def initialize(self):
        """Inicializar conexión a la base de datos"""
        try:
            self.db_pool = await asyncpg.create_pool(
                settings.database_url, min_size=5, max_size=20, command_timeout=60
            )
            logger.info("✅ Pool de base de datos inicializado")
        except Exception as e:
            logger.error(f"❌ Error inicializando pool de DB: {e}")
            raise

    async def close(self):
        """Cerrar conexiones"""
        if self.db_pool:
            await self.db_pool.close()
            logger.info("🔌 Pool de base de datos cerrado")

    def _generate_query_hash(
        self, query: str, filters: Optional[SearchFilters] = None
    ) -> str:
        """Generar hash único para consulta"""
        # Crear string canónico
        canonical = f"{query.lower().strip()}"
        if filters:
            canonical += f":{filters.city}:{filters.profession}:{filters.min_rating}:{filters.available_only}"

        # Generar hash SHA-256
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    async def search_providers(self, request: SearchRequest) -> SearchResult:
        """
        Búsqueda principal de proveedores con orquestación inteligente
        """
        start_time = time.time()
        query_hash = self._generate_query_hash(request.query, request.filters)

        # 1. Verificar caché primero
        cached_result = await cache_service.get_search_result(query_hash)
        if cached_result:
            logger.info(f"🎯 Cache HIT para query: {request.query[:50]}...")
            await self._update_metrics_async(
                request, cached_result.metadata, cache_hit=True
            )
            return cached_result

        # 2. Analizar la consulta
        query_analysis = analyze_query(request.query)
        logger.info(f"🔍 Análisis: {query_analysis}")

        # 3. Seleccionar estrategia de búsqueda
        strategy = await self._select_search_strategy(request, query_analysis)
        logger.info(f"🎯 Estrategia seleccionada: {strategy.value}")

        # 4. Ejecutar búsqueda según estrategia
        if strategy == SearchStrategy.TOKEN_BASED:
            providers = await self._search_by_tokens(request, query_analysis)
        elif strategy == SearchStrategy.FULL_TEXT:
            providers = await self._search_fulltext(request, query_analysis)
        elif strategy == SearchStrategy.HYBRID:
            providers = await self._search_hybrid(request, query_analysis)
        elif strategy == SearchStrategy.AI_ENHANCED:
            providers = await self._search_ai_enhanced(request, query_analysis)
        else:
            providers = await self._search_by_tokens(request, query_analysis)

        # 5. Aplicar filtros adicionales
        if request.filters:
            providers = await self._apply_filters(providers, request.filters)

        # 6. Ordenar y limitar resultados
        providers = self._sort_and_limit_results(
            providers, request.limit, request.offset
        )

        # 7. Crear resultado
        search_time_ms = int((time.time() - start_time) * 1000)
        metadata = SearchMetadata(
            query_tokens=query_analysis["tokens"],
            search_strategy=strategy,
            total_results=len(providers),
            search_time_ms=search_time_ms,
            confidence=self._calculate_overall_confidence(providers, query_analysis),
            used_ai_enhancement=(strategy == SearchStrategy.AI_ENHANCED),
            cache_hit=False,
            filters_applied=request.filters.model_dump() if request.filters else {},
        )

        result = SearchResult(providers=providers, metadata=metadata)

        # 8. Guardar en caché (si tiene suficientes resultados)
        if len(providers) > 0:
            await cache_service.cache_search_result(query_hash, result)

        # 9. Actualizar métricas de forma asíncrona
        await self._update_metrics_async(request, metadata, cache_hit=False)

        return result

    async def _select_search_strategy(
        self, request: SearchRequest, query_analysis: Dict[str, Any]
    ) -> SearchStrategy:
        """Seleccionar la mejor estrategia de búsqueda"""

        # Si el usuario fuerza una estrategia
        if request.preferred_strategy != SearchStrategy.HYBRID:
            return request.preferred_strategy

        # Estrategia basada en análisis de consulta
        if query_analysis["has_clear_intent"] and query_analysis["service_tokens"]:
            return SearchStrategy.TOKEN_BASED

        if len(query_analysis["tokens"]) > 5 or not query_analysis["service_tokens"]:
            return SearchStrategy.FULL_TEXT

        # Si hay pocos tokens claros pero IA está disponible
        if request.use_ai_enhancement and settings.openai_api_key:
            return SearchStrategy.AI_ENHANCED

        return SearchStrategy.HYBRID

    async def _search_by_tokens(
        self, request: SearchRequest, query_analysis: Dict[str, Any]
    ) -> List[ProviderInfo]:
        """Búsqueda por tokens (más rápida)"""
        try:
            tokens = query_analysis["service_tokens"] + query_analysis["tokens"]
            city = query_analysis.get("city")

            if not self.db_pool:
                raise Exception("Database pool not initialized")

            async with self.db_pool.acquire() as conn:
                # Usar función optimizada de PostgreSQL
                query = """
                    SELECT * FROM search_providers_by_tokens(
                        $1::TEXT[], $2::VARCHAR, $3::INTEGER, $4::INTEGER
                    )
                """
                rows = await conn.fetch(
                    query, tokens, city, request.limit, request.offset
                )

                return [self._row_to_provider_info(row) for row in rows]

        except Exception as e:
            logger.error(f"Error en búsqueda por tokens: {e}")
            return []

    async def _search_fulltext(
        self, request: SearchRequest, query_analysis: Dict[str, Any]
    ) -> List[ProviderInfo]:
        """Búsqueda full-text (para consultas complejas)"""
        try:
            city = query_analysis.get("city")

            if not self.db_pool:
                raise Exception("Database pool not initialized")

            async with self.db_pool.acquire() as conn:
                query = """
                    SELECT * FROM search_providers_fulltext(
                        $1::TEXT, $2::VARCHAR, $3::INTEGER, $4::INTEGER
                    )
                """
                rows = await conn.fetch(
                    query,
                    query_analysis["normalized_text"],
                    city,
                    request.limit,
                    request.offset,
                )

                return [self._row_to_provider_info(row) for row in rows]

        except Exception as e:
            logger.error(f"Error en búsqueda full-text: {e}")
            return []

    async def _search_hybrid(
        self, request: SearchRequest, query_analysis: Dict[str, Any]
    ) -> List[ProviderInfo]:
        """Búsqueda híbrida (combina múltiples estrategias)"""
        # Ejecutar búsquedas en paralelo
        token_task = self._search_by_tokens(request, query_analysis)
        fulltext_task = self._search_fulltext(request, query_analysis)

        try:
            token_results, fulltext_results = await asyncio.gather(
                token_task, fulltext_task, return_exceptions=True
            )

            # Combinar resultados eliminando duplicados
            all_providers = []
            seen_ids = set()

            # Priorizar resultados de tokens
            if isinstance(token_results, list):
                for provider in token_results:
                    if provider.id not in seen_ids:
                        seen_ids.add(provider.id)
                        all_providers.append(provider)

            # Agregar resultados de full-text
            if isinstance(fulltext_results, list):
                for provider in fulltext_results:
                    if provider.id not in seen_ids:
                        seen_ids.add(provider.id)
                        all_providers.append(provider)

            return all_providers

        except Exception as e:
            logger.error(f"Error en búsqueda híbrida: {e}")
            return []

    async def _search_ai_enhanced(
        self, request: SearchRequest, query_analysis: Dict[str, Any]
    ) -> List[ProviderInfo]:
        """Búsqueda mejorada con IA"""
        try:
            import openai

            if not settings.openai_api_key:
                logger.warning(
                    "⚠️ OpenAI API key no configurada, fallback a búsqueda por tokens"
                )
                return await self._search_by_tokens(request, query_analysis)

            # Mejorar consulta con IA
            enhanced_query = await self._enhance_query_with_ai(
                request.query, query_analysis
            )

            # Ejecutar búsqueda con consulta mejorada
            enhanced_analysis = analyze_query(enhanced_query)
            return await self._search_by_tokens(request, enhanced_analysis)

        except Exception as e:
            logger.error(f"Error en búsqueda AI-enhanced: {e}")
            # Fallback a búsqueda por tokens
            return await self._search_by_tokens(request, query_analysis)

    async def _enhance_query_with_ai(
        self, original_query: str, analysis: Dict[str, Any]
    ) -> str:
        """Mejorar consulta usando IA"""
        try:
            import openai

            client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

            system_prompt = """
            Eres un experto en servicios profesionales en Ecuador. Tu tarea es mejorar
            consultas de búsqueda añadiendo términos relevantes y sinónimos.

            Ejemplos:
            - "necesito doctor" → "médico doctor consulta médica"
            - "arreglo casa" → "albañil construcción reparación mantenimiento"
            - "necesito publicidad" → "marketing publicidad promoción publicidad digital"

            Solo responde con la consulta mejorada, sin explicaciones.
            """

            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"Mejora esta consulta: {original_query}",
                    },
                ],
                max_tokens=50,
                temperature=0.3,
            )

            enhanced_query = response.choices[0].message.content.strip()
            logger.info(f"🤖 IA mejoró '{original_query}' → '{enhanced_query}'")
            return enhanced_query

        except Exception as e:
            logger.warning(f"⚠️ Error mejorando consulta con IA: {e}")
            return original_query

    async def _apply_filters(
        self, providers: List[ProviderInfo], filters: SearchFilters
    ) -> List[ProviderInfo]:
        """Aplicar filtros adicionales a los resultados"""
        filtered_providers = []

        for provider in providers:
            # Filtro de disponibilidad
            if filters.available_only and not provider.available:
                continue

            # Filtro de verificación
            if filters.verified_only and not provider.verified:
                continue

            # Filtro de rating
            if provider.rating < filters.min_rating:
                continue

            # Filtro de ciudad
            if filters.city and provider.city != filters.city:
                continue

            # Filtro de profesión
            if filters.profession:
                profession_lower = filters.profession.lower()
                if not any(profession_lower in p.lower() for p in provider.professions):
                    continue

            filtered_providers.append(provider)

        return filtered_providers

    def _sort_and_limit_results(
        self, providers: List[ProviderInfo], limit: int, offset: int
    ) -> List[ProviderInfo]:
        """Ordenar y paginar resultados"""
        # Ordenar por rating (descendente) y disponibilidad
        sorted_providers = sorted(
            providers, key=lambda p: (p.available, p.rating), reverse=True
        )

        # Aplicar paginación
        start_idx = offset
        end_idx = start_idx + limit
        return sorted_providers[start_idx:end_idx]

    def _calculate_overall_confidence(
        self, providers: List[ProviderInfo], query_analysis: Dict[str, Any]
    ) -> float:
        """Calcular confianza general de los resultados"""
        if not providers:
            return 0.0

        # Factores de confianza
        avg_rating = sum(p.rating for p in providers) / len(providers)
        available_ratio = sum(1 for p in providers if p.available) / len(providers)
        verified_ratio = sum(1 for p in providers if p.verified) / len(providers)

        # Ponderación
        confidence = (
            (avg_rating / 5.0) * 0.4 + available_ratio * 0.3 + verified_ratio * 0.3
        )

        return min(1.0, confidence)

    def _row_to_provider_info(self, row) -> ProviderInfo:
        """Convertir fila de BD a ProviderInfo"""
        provider_data = row["provider_data"]

        return ProviderInfo(
            id=str(row["provider_id"]),
            phone_number=provider_data.get("phone_number", ""),
            full_name=provider_data.get("full_name", ""),
            city=provider_data.get("city"),
            rating=float(provider_data.get("rating", 0.0)),
            available=provider_data.get("available", True),
            verified=provider_data.get("verified", False),
            professions=provider_data.get("professions", []),
            services=provider_data.get("services", []),
            years_of_experience=provider_data.get("years_of_experience"),
            created_at=provider_data.get("created_at", datetime.now()),
        )

    async def _update_metrics_async(
        self, request: SearchRequest, metadata: SearchMetadata, cache_hit: bool
    ):
        """Actualizar métricas de forma asíncrona (no bloquear)"""
        try:
            # Incrementar contadores básicos
            await cache_service.increment_counter("search_total")
            if cache_hit:
                await cache_service.increment_counter("cache_hits")
            else:
                await cache_service.increment_counter("cache_misses")

            if metadata.used_ai_enhancement:
                await cache_service.increment_counter("ai_enhancements")

            # Agregar a consultas populares
            await cache_service.add_query_to_popular(request.query)

        except Exception as e:
            logger.warning(f"⚠️ Error actualizando métricas: {e}")

    async def get_suggestions(self, partial_query: str, limit: int = 5) -> List[str]:
        """Obtener sugerencias de autocompletado"""
        try:
            # Verificar caché
            cached_suggestions = await cache_service.get_suggestions(partial_query)
            if cached_suggestions:
                return cached_suggestions

            # Generar sugerencias basadas en consultas populares
            popular_queries = await cache_service.get_popular_queries(limit * 2)

            suggestions = []
            for query_info in popular_queries:
                query = query_info["query"]
                if partial_query.lower() in query.lower():
                    suggestions.append(query)
                    if len(suggestions) >= limit:
                        break

            # Guardar en caché
            await cache_service.cache_suggestions(partial_query, suggestions)

            return suggestions

        except Exception as e:
            logger.error(f"Error obteniendo sugerencias: {e}")
            return []

    async def health_check(self) -> Dict[str, Any]:
        """Verificar salud del servicio de búsqueda"""
        health_info = {
            "database_connected": False,
            "cache_connected": await cache_service.health_check(),
            "search_service_ready": False,
            "last_check": datetime.now().isoformat(),
        }

        try:
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                    health_info["database_connected"] = True
        except Exception as e:
            logger.error(f"Error health check DB: {e}")

        health_info["search_service_ready"] = (
            health_info["database_connected"] and health_info["cache_connected"]
        )

        return health_info


# Instancia global del servicio de búsqueda
search_service = SearchService()
