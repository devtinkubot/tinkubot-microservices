"""
Servicio principal de búsqueda para Search Service (embeddings-only).
"""

import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI
from supabase import Client, create_client

from app.config import settings
from models.schemas import (
    ProviderInfo,
    SearchFilters,
    SearchMetadata,
    SearchRequest,
    SearchResult,
)
from services.cache_service import cache_service
from utils.text_processor import TextProcessor, analyze_query

logger = logging.getLogger(__name__)
SUPABASE_TIMEOUT_SECONDS = (
    float(getattr(settings, "search_timeout_ms", 5000) or 5000) / 1000.0
)
SLOW_QUERY_THRESHOLD_MS = int(getattr(settings, "search_timeout_ms", 5000) or 5000)


class EmbeddingUnavailableError(Exception):
    """Error controlado cuando embeddings no está disponible."""


class SearchService:
    """Servicio de búsqueda embeddings-only."""

    def __init__(self):
        self.supabase: Optional[Client] = None
        self.openai_client: Optional[AsyncOpenAI] = None
        self.text_processor = TextProcessor()
        self.intent_aliases: Dict[str, set[str]] = self._load_intent_aliases()
        self._openai_semaphore = asyncio.Semaphore(
            int(getattr(settings, "max_openai_concurrency", 5) or 5)
        )

    async def _run_supabase(self, op, label: str):
        """
        Ejecuta operación Supabase en executor para no bloquear el loop,
        con timeout y log de lentos.
        """
        loop = asyncio.get_running_loop()
        start = perf_counter()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, op), timeout=SUPABASE_TIMEOUT_SECONDS
            )
        finally:
            elapsed_ms = (perf_counter() - start) * 1000
            if elapsed_ms >= SLOW_QUERY_THRESHOLD_MS:
                logger.info(
                    "perf_supabase",
                    extra={"op": label, "elapsed_ms": round(elapsed_ms, 2)},
                )

    async def initialize(self):
        """Inicializar conexión a Supabase y OpenAI (obligatoria para embeddings)."""
        try:
            self.supabase = create_client(
                settings.supabase_url, settings.supabase_service_key
            )
            logger.info("✅ Cliente Supabase inicializado")

            if not settings.openai_api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY es obligatoria en modo embeddings-only"
                )

            self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
            logger.info("✅ Cliente OpenAI inicializado")

        except Exception as e:
            logger.error(f"❌ Error inicializando servicios: {e}")
            raise

    async def close(self):
        """Cerrar conexiones."""
        if self.supabase:
            logger.info("🔌 Cliente Supabase cerrado")

    def _generate_query_hash(
        self, query: str, filters: Optional[SearchFilters] = None
    ) -> str:
        """Generar hash único para consulta."""
        canonical = f"{query.lower().strip()}"
        if filters:
            canonical += (
                f":{filters.city}:{filters.profession}:"
                f"{filters.min_rating}:{filters.verified_only}"
            )

        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    async def search_providers(self, request: SearchRequest) -> SearchResult:
        """Búsqueda principal embeddings-only."""
        start_time = time.time()
        query_hash = self._generate_query_hash(request.query, request.filters)

        cached_result = await cache_service.get_search_result(query_hash)
        if cached_result:
            logger.info(f"🎯 Cache HIT para query: {request.query[:50]}...")
            await self._update_metrics_async(
                request, cached_result.metadata, cache_hit=True
            )
            return cached_result

        query_analysis = analyze_query(request.query)
        logger.info(f"🔍 Análisis: {query_analysis}")
        base_intent_tokens = query_analysis.get("service_tokens") or query_analysis.get(
            "tokens", []
        )
        base_city = query_analysis.get("city")

        providers = await self._search_by_embeddings(request)

        if request.filters:
            providers = await self._apply_filters(providers, request.filters)

        providers = self._filter_by_intent(providers, base_intent_tokens, base_city)

        providers = self._sort_and_limit_results(
            providers, request.limit, request.offset
        )

        search_time_ms = int((time.time() - start_time) * 1000)
        metadata = SearchMetadata(
            query_tokens=query_analysis["tokens"],
            search_strategy="embeddings",
            total_results=len(providers),
            search_time_ms=search_time_ms,
            confidence=self._calculate_overall_confidence(providers, query_analysis),
            used_embeddings=True,
            cache_hit=False,
            filters_applied=request.filters.model_dump() if request.filters else {},
        )

        result = SearchResult(providers=providers, metadata=metadata)

        if len(providers) > 0:
            await cache_service.cache_search_result(query_hash, result)

        await self._update_metrics_async(request, metadata, cache_hit=False)

        return result

    async def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """Genera embedding para el texto de consulta con caché en Redis."""
        if not self.openai_client or not text:
            return None

        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        cache_key = f"embedding:{settings.embeddings_model}:{text_hash}"

        try:
            if cache_service.is_connected and cache_service.redis_client:
                cached = await cache_service.redis_client.get(cache_key)
                if cached:
                    logger.info(f"✅ Cache HIT embedding para query: {text[:50]}...")
                    return json.loads(cached)
        except Exception as exc:
            logger.warning(f"⚠️ Error verificando caché embedding: {exc}")

        max_attempts = max(1, int(settings.embeddings_retry_attempts or 0) + 1)
        backoff_seconds = max(0, int(settings.embeddings_retry_backoff_ms or 0)) / 1000

        for attempt in range(1, max_attempts + 1):
            try:
                async with self._openai_semaphore:
                    embedding = await asyncio.wait_for(
                        self._openai_embed(text),
                        timeout=settings.embeddings_timeout_seconds,
                    )

                try:
                    if (
                        cache_service.is_connected
                        and cache_service.redis_client
                        and embedding
                    ):
                        await cache_service.redis_client.setex(
                            cache_key,
                            3600,
                            json.dumps(embedding),
                        )
                except Exception as exc:
                    logger.warning(f"⚠️ Error guardando caché embedding: {exc}")

                return embedding
            except asyncio.TimeoutError:
                logger.warning(
                    "⚠️ Timeout generando embedding (intento %s/%s, timeout=%ss)",
                    attempt,
                    max_attempts,
                    settings.embeddings_timeout_seconds,
                )
            except Exception as exc:
                logger.warning(
                    "⚠️ Error generando embedding (intento %s/%s): %s",
                    attempt,
                    max_attempts,
                    exc,
                )

            if attempt < max_attempts and backoff_seconds > 0:
                await asyncio.sleep(backoff_seconds * attempt)

        return None

    async def _openai_embed(self, text: str) -> List[float]:
        response = await self.openai_client.embeddings.create(
            model=settings.embeddings_model,
            input=text,
        )
        return response.data[0].embedding

    async def _search_by_embeddings(self, request: SearchRequest) -> List[ProviderInfo]:
        """Búsqueda por embeddings usando provider_services."""
        if not self.supabase:
            raise RuntimeError("Supabase client not initialized")

        embedding = await self._generate_embedding(request.query)
        if not embedding:
            raise EmbeddingUnavailableError(
                "No fue posible generar embeddings para la consulta"
            )

        city = None
        verified_only = True
        if request.filters:
            city = request.filters.city
            verified_only = request.filters.verified_only

        match_count = max(settings.vector_top_k, request.limit + request.offset)
        params = {
            "query_embedding": embedding,
            "match_count": match_count,
            "city_filter": f"%{city}%" if city else None,
            "verified_only": verified_only,
        }

        response = await self._run_supabase(
            lambda: self.supabase.rpc("match_provider_services", params).execute(),
            label="providers.search_embeddings",
        )

        providers: List[ProviderInfo] = []
        if response and response.data:
            for row in response.data:
                providers.append(self._dict_to_provider_info_from_vector(row))
        return providers

    def _dict_to_provider_info_from_vector(self, row: Dict[str, Any]) -> ProviderInfo:
        """Convertir resultado vectorial a ProviderInfo."""
        services = row.get("services") or []
        return ProviderInfo(
            id=str(row.get("provider_id") or row.get("id")),
            phone_number=row.get("phone", ""),
            real_phone=row.get("real_phone"),
            full_name=row.get("full_name", ""),
            city=row.get("city"),
            rating=float(row.get("rating", 0.0)),
            available=self._normalize_available(
                row.get("available"), row.get("verified")
            ),
            verified=row.get("verified", False),
            professions=[],
            services=services,
            years_of_experience=row.get("experience_years"),
            created_at=row.get("created_at", datetime.now()),
            social_media_url=row.get("social_media_url"),
            social_media_type=row.get("social_media_type"),
            face_photo_url=row.get("face_photo_url"),
        )

    def _load_intent_aliases(self) -> Dict[str, set[str]]:
        """Carga alias de intención desde archivo JSON (configurable)."""
        config_path = (
            Path(__file__).resolve().parents[1] / "app" / "config" / "intent_aliases.json"
        )
        if not config_path.exists():
            return {}

        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            aliases: Dict[str, set[str]] = {}
            for key, values in data.items():
                if isinstance(values, list):
                    aliases[key.lower()] = {v.lower() for v in values if v}
            logger.info("🔧 Alias de intención cargados")
            return aliases
        except Exception as exc:  # pragma: no cover
            logger.warning(f"No se pudieron cargar alias de intención: {exc}")
            return {}

    def _filter_by_intent(
        self,
        providers: List[ProviderInfo],
        intent_tokens: List[str],
        city: Optional[str],
    ) -> List[ProviderInfo]:
        """Filtra resultados que no coinciden con los tokens clave del servicio."""
        if not intent_tokens:
            return providers

        tokens: set[str] = set()
        for raw in intent_tokens:
            if not raw:
                continue
            base = raw.lower()
            if city and base == city.lower():
                continue
            aliases = self.intent_aliases.get(base, set())
            tokens.update({base, *aliases})

        tokens_to_match = [token for token in tokens if len(token) >= 4]

        if not tokens_to_match:
            return providers

        filtered: List[ProviderInfo] = []
        for provider in providers:
            professions_text = " ".join(provider.professions or []).lower()
            services = " ".join(provider.services or []).lower()
            if any(
                token in professions_text or token in services
                for token in tokens_to_match
            ):
                filtered.append(provider)
        return filtered

    async def _apply_filters(
        self, providers: List[ProviderInfo], filters: SearchFilters
    ) -> List[ProviderInfo]:
        """Aplicar filtros adicionales a los resultados."""
        filtered_providers = []

        for provider in providers:
            if filters.verified_only and not provider.verified:
                continue

            if provider.rating < filters.min_rating:
                continue

            if filters.city and provider.city and provider.city.lower() != filters.city.lower():
                continue

            if filters.profession:
                profession_lower = filters.profession.lower()
                if not any(profession_lower in p.lower() for p in provider.professions):
                    continue

            filtered_providers.append(provider)

        return filtered_providers

    def _sort_and_limit_results(
        self,
        providers: List[ProviderInfo],
        limit: int,
        offset: int,
    ) -> List[ProviderInfo]:
        """Aplicar paginación preservando el orden de similitud vectorial."""
        start_idx = offset
        end_idx = start_idx + limit
        return list(providers)[start_idx:end_idx]

    def _calculate_overall_confidence(
        self, providers: List[ProviderInfo], query_analysis: Dict[str, Any]
    ) -> float:
        """Calcular confianza general de los resultados."""
        if not providers:
            return 0.0

        avg_rating = sum(p.rating for p in providers) / len(providers)
        verified_ratio = sum(1 for p in providers if p.verified) / len(providers)
        confidence = (avg_rating / 5.0) * 0.6 + verified_ratio * 0.4

        return min(1.0, confidence)

    def _normalize_available(self, available: Any, verified: Any) -> bool:
        """
        Normaliza el estado de disponibilidad. Si no viene en la BD (None),
        se asume True o el valor de verificación para evitar descartar resultados.
        """
        if available is None:
            return bool(verified if verified is not None else True)
        return bool(available)

    async def _update_metrics_async(
        self, request: SearchRequest, metadata: SearchMetadata, cache_hit: bool
    ):
        """Actualizar métricas de forma asíncrona (no bloquear)."""
        try:
            await cache_service.increment_counter("search_total")
            if cache_hit:
                await cache_service.increment_counter("cache_hits")
            else:
                await cache_service.increment_counter("cache_misses")

            if metadata.used_embeddings:
                await cache_service.increment_counter("embeddings_searches")

            await cache_service.add_query_to_popular(request.query)

        except Exception as e:
            logger.warning(f"⚠️ Error actualizando métricas: {e}")

    async def get_suggestions(self, partial_query: str, limit: int = 5) -> List[str]:
        """Obtener sugerencias de autocompletado."""
        try:
            cached_suggestions = await cache_service.get_suggestions(partial_query)
            if cached_suggestions:
                return cached_suggestions

            popular_queries = await cache_service.get_popular_queries(limit * 2)

            suggestions = []
            for query_info in popular_queries:
                query = query_info["query"]
                if partial_query.lower() in query.lower():
                    suggestions.append(query)
                    if len(suggestions) >= limit:
                        break

            await cache_service.cache_suggestions(partial_query, suggestions)

            return suggestions

        except Exception as e:
            logger.error(f"Error obteniendo sugerencias: {e}")
            return []

    async def health_check(self) -> Dict[str, Any]:
        """Verificar salud del servicio de búsqueda sin bloquear el loop."""
        health_info = {
            "database_connected": False,
            "redis_connected": await cache_service.health_check(),
            "search_service_ready": False,
            "openai_configured": bool(self.openai_client),
            "last_check": datetime.now().isoformat(),
        }

        if self.supabase:
            try:
                await self._run_supabase(
                    lambda: self.supabase.table("providers").select("id").limit(1).execute(),
                    label="providers.health_check",
                )
                health_info["database_connected"] = True
            except Exception as e:
                logger.warning(f"Health check Supabase degradado: {e}")

        health_info["search_service_ready"] = (
            health_info["database_connected"]
            and health_info["redis_connected"]
            and health_info["openai_configured"]
        )

        return health_info


# Instancia global del servicio de búsqueda
search_service = SearchService()
