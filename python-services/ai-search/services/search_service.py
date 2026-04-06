"""
Servicio principal de búsqueda para Search Service (embeddings-only).
"""

import asyncio
import hashlib
import json
import logging
import re
import time
import unicodedata
from datetime import datetime
from time import perf_counter
from typing import Any, Dict, List, Optional

from app.config import settings
from models.schemas import (
    ProviderInfo,
    SearchFilters,
    SearchMetadata,
    SearchRequest,
    SearchResult,
)
from openai import AsyncOpenAI
from services.cache_service import cache_service
from supabase import Client, create_client
from utils.text_processor import analyze_query

logger = logging.getLogger(__name__)
SUPABASE_TIMEOUT_SECONDS = settings.search_timeout_ms / 1000.0
SLOW_QUERY_THRESHOLD_MS = settings.search_timeout_ms


class EmbeddingUnavailableError(Exception):
    """Error controlado cuando embeddings no está disponible."""


class SearchService:
    """Servicio de búsqueda embeddings-only."""

    def __init__(self):
        self.supabase: Optional[Client] = None
        self.openai_client: Optional[AsyncOpenAI] = None
        self._openai_semaphore = asyncio.Semaphore(
            settings.max_openai_concurrency
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

    @staticmethod
    def _normalize_text(text: Optional[str]) -> str:
        if not text:
            return ""
        normalized = unicodedata.normalize("NFD", text.lower().strip())
        no_accents = "".join(
            ch for ch in normalized if unicodedata.category(ch) != "Mn"
        )
        clean = re.sub(r"[^a-z0-9\s]", " ", no_accents)
        return re.sub(r"\s+", " ", clean).strip()

    def _build_effective_query(self, request: SearchRequest) -> str:
        context = getattr(request, "context", None) or {}
        search_profile = context.get("search_profile")
        if not isinstance(search_profile, dict):
            search_profile = {}
        service_candidate = str(
            context.get("normalized_service")
            or context.get("service_candidate")
            or search_profile.get("primary_service")
            or ""
        ).strip()
        service_summary = str(
            context.get("service_summary")
            or search_profile.get("service_summary")
            or service_candidate
            or ""
        ).strip()
        domain_text = str(
            context.get("domain_code") or context.get("domain") or ""
        ).strip()
        category_text = str(
            context.get("category_name") or context.get("category") or ""
        ).strip()

        query_parts: List[str] = []
        if service_summary:
            query_parts.append(service_summary)
        elif service_candidate:
            query_parts.append(service_candidate)
        if domain_text:
            query_parts.append(domain_text)
        if category_text:
            query_parts.append(category_text)
        if not query_parts and request.query.strip():
            query_parts.append(request.query.strip())

        deduped_parts: List[str] = []
        seen = set()
        for part in query_parts:
            normalized_part = self._normalize_text(part)
            if not normalized_part or normalized_part in seen:
                continue
            seen.add(normalized_part)
            deduped_parts.append(part)

        return " ".join(deduped_parts) if deduped_parts else request.query

    @staticmethod
    def _extract_signals_text(context: Dict[str, Any]) -> str:
        raw_signals = context.get("signals") or []
        if isinstance(raw_signals, str):
            raw_signals = [raw_signals]
        return " ".join(
            str(signal).strip() for signal in raw_signals if str(signal).strip()
        )

    @staticmethod
    def _tokenize_text(value: Optional[str]) -> set[str]:
        if not value:
            return set()
        normalized = SearchService._normalize_text(value)
        return {token for token in normalized.split() if len(token) >= 3}

    @staticmethod
    def _token_overlap(left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        union = left | right
        if not union:
            return 0.0
        return len(left & right) / len(union)

    def _build_context_profile(self, request: SearchRequest) -> Dict[str, Any]:
        context = getattr(request, "context", None) or {}
        search_profile = context.get("search_profile")
        if not isinstance(search_profile, dict):
            search_profile = {}
        service_candidate = str(
            context.get("normalized_service")
            or context.get("service_candidate")
            or search_profile.get("primary_service")
            or request.query
            or ""
        ).strip()
        service_summary = str(
            context.get("service_summary")
            or search_profile.get("service_summary")
            or service_candidate
            or ""
        ).strip()
        problem_description = str(context.get("problem_description") or "").strip()
        domain_text = str(
            context.get("domain_code") or context.get("domain") or ""
        ).strip()
        category_text = str(
            context.get("category_name") or context.get("category") or ""
        ).strip()

        query_text = " ".join(
            part
            for part in [
                service_summary,
                service_candidate,
                domain_text,
                category_text,
            ]
            if part
        )
        signal_text = self._extract_signals_text(context)

        return {
            "service_candidate": service_candidate,
            "service_summary": service_summary,
            "problem_description": problem_description,
            "domain_text": domain_text,
            "category_text": category_text,
            "service_tokens": self._tokenize_text(service_summary or service_candidate),
            "problem_tokens": self._tokenize_text(problem_description),
            "domain_tokens": self._tokenize_text(domain_text),
            "category_tokens": self._tokenize_text(category_text),
            "query_tokens": self._tokenize_text(query_text),
            "signals_text": signal_text,
            "signals_tokens": self._tokenize_text(signal_text),
        }

    def _compute_semantic_alignment_score(
        self,
        *,
        request: SearchRequest,
        row: Dict[str, Any],
        similarity_score: Optional[float],
        retrieval_score: Optional[float],
    ) -> float:
        context_profile = self._build_context_profile(request)

        provider_service_text = " ".join(
            part.strip()
            for part in [
                str(row.get("matched_service_name") or "").strip(),
                str(row.get("matched_service_summary") or "").strip(),
                " ".join(str(service).strip() for service in (row.get("services") or [])),
            ]
            if part.strip()
        )
        provider_domain_text = str(row.get("domain_code") or "").strip()
        provider_category_text = str(row.get("category_name") or "").strip()

        provider_service_tokens = self._tokenize_text(provider_service_text)
        provider_domain_tokens = self._tokenize_text(provider_domain_text)
        provider_category_tokens = self._tokenize_text(provider_category_text)
        provider_query_tokens = self._tokenize_text(
            " ".join(
                part
                for part in [
                    provider_service_text,
                    provider_domain_text,
                    provider_category_text,
                ]
                if part
            )
        )

        service_overlap = self._token_overlap(
            context_profile["service_tokens"], provider_service_tokens
        )
        problem_overlap = self._token_overlap(
            context_profile["problem_tokens"], provider_service_tokens
        )
        domain_overlap = self._token_overlap(
            context_profile["domain_tokens"], provider_domain_tokens
        )
        category_overlap = self._token_overlap(
            context_profile["category_tokens"], provider_category_tokens
        )
        query_overlap = self._token_overlap(
            context_profile["query_tokens"], provider_query_tokens
        )

        taxonomy_overlap = max(
            domain_overlap,
            category_overlap,
            (domain_overlap + category_overlap) / 2.0
            if (context_profile["domain_tokens"] or context_profile["category_tokens"])
            else 0.0,
        )

        signals_overlap = self._token_overlap(
            context_profile["signals_tokens"], provider_service_tokens
        )
        compatibility_score = (
            service_overlap * 0.39
            + problem_overlap * 0.20
            + taxonomy_overlap * 0.20
            + query_overlap * 0.09
            + signals_overlap * 0.07
        )

        normalized_service_candidate = self._normalize_text(
            context_profile["service_candidate"]
        )
        if normalized_service_candidate and normalized_service_candidate in self._normalize_text(
            provider_service_text
        ):
            compatibility_score = max(compatibility_score, 0.88)

        if context_profile["domain_tokens"] and provider_domain_tokens and domain_overlap == 0:
            compatibility_score -= 0.08
        if (
            context_profile["category_tokens"]
            and provider_category_tokens
            and category_overlap == 0
        ):
            compatibility_score -= 0.05
        if (
            context_profile["service_tokens"]
            and provider_service_tokens
            and service_overlap == 0
            and problem_overlap == 0
            and taxonomy_overlap == 0
        ):
            compatibility_score -= 0.12

        compatibility_score = max(0.0, min(1.0, compatibility_score))
        similarity = max(0.0, min(1.0, float(similarity_score or 0.0)))
        retrieval = max(0.0, min(1.0, float(retrieval_score or 0.0)))

        semantic_alignment_score = (
            retrieval * 0.52 + similarity * 0.18 + compatibility_score * 0.30
        )
        return max(0.0, min(1.0, semantic_alignment_score))

    def _rank_by_semantic_alignment(
        self, request: SearchRequest, providers: List[ProviderInfo]
    ) -> List[ProviderInfo]:
        if not providers:
            return providers

        context = getattr(request, "context", None) or {}
        has_structured_context = bool(
            context.get("service_candidate")
            or context.get("normalized_service")
            or context.get("domain_code")
            or context.get("domain")
            or context.get("category_name")
            or context.get("category")
        )

        ranked = providers
        if has_structured_context:
            filtered = [
                provider
                for provider in ranked
                if (
                    provider.semantic_alignment_score is None
                    or provider.semantic_alignment_score >= 0.30
                )
            ]
            if filtered:
                ranked = filtered

        return sorted(
            ranked,
            key=lambda provider: (
                float(provider.semantic_alignment_score or 0.0),
                float(provider.retrieval_score or 0.0),
                float(provider.similarity_score or 0.0),
                float(provider.rating or 0.0),
            ),
            reverse=True,
        )

    def _generate_query_hash(self, request: SearchRequest, effective_query: str) -> str:
        """Generar hash único para consulta."""
        canonical = f"{effective_query.lower().strip()}"
        if request.filters:
            canonical += (
                f":{request.filters.city}:"
                f"{request.filters.min_rating}"
            )
        context = request.context or {}
        search_profile = context.get("search_profile")
        if not isinstance(search_profile, dict):
            search_profile = {}
        service_summary = str(
            context.get("service_summary")
            or search_profile.get("service_summary")
            or context.get("service_candidate")
            or search_profile.get("primary_service")
            or ""
        ).lower().strip()
        canonical += (
            f":{service_summary}:"
            f"{str(context.get('normalized_service') or context.get('service_candidate') or search_profile.get('primary_service') or '').lower().strip()}:"
            f"{str(context.get('domain_code') or context.get('domain') or '').lower().strip()}:"
            f"{str(context.get('category_name') or context.get('category') or '').lower().strip()}"
        )
        signals_text = self._extract_signals_text(context).lower().strip()
        if signals_text:
            canonical += f":{signals_text}"

        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    async def search_providers(self, request: SearchRequest) -> SearchResult:
        """Búsqueda principal embeddings-only."""
        start_time = time.time()
        effective_query = self._build_effective_query(request)
        query_hash = self._generate_query_hash(request, effective_query)

        cached_result = await cache_service.get_search_result(query_hash)
        if cached_result:
            logger.info(
                "🎯 Cache HIT para query efectiva: %s...",
                effective_query[:50],
            )
            await self._update_metrics_async(
                request, cached_result.metadata, cache_hit=True
            )
            return cached_result

        query_analysis = analyze_query(effective_query)
        logger.info(
            "🔍 Query original='%s' | efectiva='%s' | análisis=%s",
            request.query,
            effective_query,
            query_analysis,
        )

        providers = await self._search_by_embeddings(request, effective_query)

        if request.filters:
            providers = await self._apply_filters(providers, request.filters)

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

    async def _search_by_embeddings(
        self, request: SearchRequest, effective_query: str
    ) -> List[ProviderInfo]:
        """Búsqueda por embeddings usando provider_services."""
        if not self.supabase:
            raise RuntimeError("Supabase client not initialized")

        embedding = await self._generate_embedding(effective_query)
        if not embedding:
            raise EmbeddingUnavailableError(
                "No fue posible generar embeddings para la consulta"
            )

        city = None
        if request.filters:
            city = request.filters.city

        match_count = max(settings.vector_top_k, request.limit + request.offset)
        params = {
            "query_embedding": embedding,
            "match_count": match_count,
            "city_filter": f"%{city}%" if city else None,
            "verified_only": False,
            "similarity_threshold": settings.vector_similarity_threshold,
        }

        providers: List[ProviderInfo] = []
        distances: List[float] = []
        response = await self._run_supabase(
            lambda: self.supabase.rpc("match_provider_services", params).execute(),
            label="providers.search_embeddings",
        )

        if response and response.data:
            for row in response.data:
                distance = row.get("distance")
                if isinstance(distance, (int, float)):
                    distances.append(float(distance))
                providers.append(
                    self._dict_to_provider_info_from_vector(row, request=request)
                )

        min_distance = min(distances) if distances else None
        max_distance = max(distances) if distances else None
        logger.info(
            "search_embeddings_rpc query=%r match_count=%s threshold=%.2f returned=%s city=%r min_distance=%s max_distance=%s",
            effective_query[:120],
            match_count,
            settings.vector_similarity_threshold,
            len(providers),
            city,
            f"{min_distance:.4f}" if min_distance is not None else "n/a",
            f"{max_distance:.4f}" if max_distance is not None else "n/a",
        )
        return self._rank_by_semantic_alignment(request, providers)

    def _dict_to_provider_info_from_vector(
        self, row: Dict[str, Any], request: Optional[SearchRequest] = None
    ) -> ProviderInfo:
        """Convertir resultado vectorial a ProviderInfo."""
        services = row.get("services") or []
        distance_raw = row.get("distance")
        similarity_score = None
        try:
            if distance_raw is not None:
                similarity_score = max(0.0, min(1.0, 1.0 - float(distance_raw)))
        except (TypeError, ValueError):
            similarity_score = None
        retrieval_score = self._calculate_retrieval_score(
            similarity_score=similarity_score,
            rating=float(row.get("rating", 0.0)),
            classification_confidence=row.get("classification_confidence"),
        )
        semantic_alignment_score = (
            self._compute_semantic_alignment_score(
                request=request,
                row=row,
                similarity_score=similarity_score,
                retrieval_score=retrieval_score,
            )
            if request is not None
            else None
        )
        return ProviderInfo(
            id=str(row.get("provider_id") or row.get("id")),
            phone_number=row.get("phone", ""),
            real_phone=row.get("real_phone"),
            full_name=row.get("full_name", ""),
            document_first_names=row.get("document_first_names"),
            document_last_names=row.get("document_last_names"),
            display_name=row.get("display_name"),
            city=row.get("city"),
            rating=float(row.get("rating") or 5.0),
            available=self._normalize_available(row.get("available")),
            verified=row.get("verified", False),
            services=services,
            service_summaries=row.get("service_summaries"),
            experience_range=row.get("experience_range"),
            created_at=row.get("created_at", datetime.now()),
            similarity_score=similarity_score,
            semantic_alignment_score=semantic_alignment_score,
            matched_service_name=row.get("matched_service_name"),
            matched_service_summary=row.get("matched_service_summary"),
            domain_code=row.get("domain_code"),
            category_name=row.get("category_name"),
            classification_confidence=row.get("classification_confidence"),
            retrieval_score=retrieval_score,
            social_media_url=row.get("social_media_url"),
            social_media_type=row.get("social_media_type"),
            face_photo_url=row.get("face_photo_url"),
        )

    async def _apply_filters(
        self, providers: List[ProviderInfo], filters: SearchFilters
    ) -> List[ProviderInfo]:
        """Aplicar filtros adicionales a los resultados."""
        filtered_providers = []

        for provider in providers:
            if provider.rating < filters.min_rating:
                continue

            if (
                filters.city
                and provider.city
                and provider.city.lower() != filters.city.lower()
            ):
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
        return providers[start_idx:end_idx]

    def _calculate_overall_confidence(
        self, providers: List[ProviderInfo], query_analysis: Dict[str, Any]
    ) -> float:
        """Calcular confianza general de los resultados."""
        if not providers:
            return 0.0

        avg_rating = sum(p.rating for p in providers) / len(providers)
        return min(1.0, avg_rating / 5.0)

    def _calculate_retrieval_score(
        self,
        *,
        similarity_score: Optional[float],
        rating: float,
        classification_confidence: Any,
    ) -> float:
        similarity = float(similarity_score or 0.0)
        try:
            classification = max(0.0, min(1.0, float(classification_confidence or 0.0)))
        except (TypeError, ValueError):
            classification = 0.0
        score = (
            similarity * 0.82
            + classification * 0.18
        )
        return max(0.0, min(1.0, score))

    def _normalize_available(self, available: Any) -> bool:
        """
        Normaliza el estado de disponibilidad. Si no viene en la BD (None),
        se asume True para evitar descartar resultados.
        """
        if available is None:
            return True
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
                    lambda: self.supabase.table("providers")
                    .select("id")
                    .limit(1)
                    .execute(),
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
