"""
Servicio principal de búsqueda para Search Service
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

from models.schemas import (
    ProviderInfo,
    SearchFilters,
    SearchMetadata,
    SearchRequest,
    SearchResult,
    SearchStrategy,
)
from openai import AsyncOpenAI
from services.cache_service import cache_service
from shared_lib.config import settings
from supabase import Client, create_client
from utils.text_processor import SERVICE_KEYWORDS, TextProcessor, analyze_query

logger = logging.getLogger(__name__)
SUPABASE_TIMEOUT_SECONDS = float(getattr(settings, "search_timeout_ms", 5000) or 5000) / 1000.0
SLOW_QUERY_THRESHOLD_MS = int(getattr(settings, "search_timeout_ms", 5000) or 5000)


class SearchService:
    """Servicio de búsqueda optimizado con múltiples estrategias"""

    def __init__(self):
        self.supabase: Optional[Client] = None
        self.openai_client: Optional[AsyncOpenAI] = None
        self.text_processor = TextProcessor()
        self.intent_aliases: Dict[str, set[str]] = self._load_intent_aliases()
        self._openai_semaphore = asyncio.Semaphore(int(getattr(settings, "max_openai_concurrency", 5) or 5))

    async def _run_supabase(self, op, label: str):
        """
        Ejecuta operación Supabase en executor para no bloquear el loop, con timeout y log de lentos.
        """
        loop = asyncio.get_running_loop()
        start = perf_counter()
        try:
            return await asyncio.wait_for(loop.run_in_executor(None, op), timeout=SUPABASE_TIMEOUT_SECONDS)
        finally:
            elapsed_ms = (perf_counter() - start) * 1000
            if elapsed_ms >= SLOW_QUERY_THRESHOLD_MS:
                logger.info(
                    "perf_supabase",
                    extra={"op": label, "elapsed_ms": round(elapsed_ms, 2)},
                )

    async def initialize(self):
        """Inicializar conexión a Supabase y OpenAI"""
        try:
            self.supabase = create_client(settings.supabase_url, settings.supabase_service_key)
            logger.info("✅ Cliente Supabase inicializado")

            # Inicializar cliente OpenAI
            if settings.openai_api_key:
                self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
                logger.info("✅ Cliente OpenAI inicializado")
            else:
                logger.warning("⚠️ API key de OpenAI no configurada")

        except Exception as e:
            logger.error(f"❌ Error inicializando servicios: {e}")
            raise

    async def close(self):
        """Cerrar conexiones"""
        if self.supabase:
            # Supabase client doesn't need explicit closing
            logger.info("🔌 Cliente Supabase cerrado")

    def _generate_query_hash(self, query: str, filters: Optional[SearchFilters] = None) -> str:
        """Generar hash único para consulta"""
        # Crear string canónico
        canonical = f"{query.lower().strip()}"
        if filters:
            canonical += f":{filters.city}:{filters.profession}:{filters.min_rating}:{filters.verified_only}"

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
            await self._update_metrics_async(request, cached_result.metadata, cache_hit=True)
            return cached_result

        # 2. Analizar la consulta
        query_analysis = analyze_query(request.query)
        logger.info(f"🔍 Análisis: {query_analysis}")
        base_intent_tokens = query_analysis.get("service_tokens") or query_analysis.get("tokens", [])
        base_city = query_analysis.get("city")

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

        # 5.1. Filtrar por intención original para evitar falsos positivos de expansión
        providers = self._filter_by_intent(providers, base_intent_tokens, base_city)

        # 6. Ordenar y limitar resultados
        providers = self._sort_and_limit_results(providers, request.limit, request.offset)

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

    async def _select_search_strategy(self, request: SearchRequest, query_analysis: Dict[str, Any]) -> SearchStrategy:
        """Seleccionar estrategia AI-first"""

        ai_available = bool(settings.openai_api_key)

        # Respetar estrategia preferida explícita cuando sea posible
        if request.preferred_strategy == SearchStrategy.AI_ENHANCED:
            if request.use_ai_enhancement and ai_available:
                return SearchStrategy.AI_ENHANCED
            # Sin API key, caerá a tokens
        elif request.preferred_strategy == SearchStrategy.HYBRID:
            return SearchStrategy.HYBRID
        elif request.preferred_strategy == SearchStrategy.FULL_TEXT:
            return SearchStrategy.FULL_TEXT

        # Default: priorizar IA si está habilitada y disponible, si no, tokens
        if request.use_ai_enhancement and ai_available:
            return SearchStrategy.AI_ENHANCED

        return SearchStrategy.TOKEN_BASED

    async def _search_by_tokens(self, request: SearchRequest, query_analysis: Dict[str, Any]) -> List[ProviderInfo]:
        """Búsqueda por tokens (más rápida)"""
        try:
            slow_start = perf_counter()
            # Usar tokens de servicio y generales para no perder términos específicos
            tokens_raw = list(
                {
                    *(query_analysis.get("service_tokens") or []),
                    *(query_analysis.get("tokens") or []),
                }
            )
            # Usar tokens únicos para evitar duplicados que sobrecargan la consulta SQL
            tokens = list({t for t in tokens_raw if (len(t) >= 4 or t in SERVICE_KEYWORDS)})
            city = query_analysis.get("city")

            if not self.supabase:
                raise Exception("Supabase client not initialized")

            # Construir consulta con Supabase
            query = self.supabase.table("providers").select("*", count="exact")

            # Filtrar por verified=true
            query = query.eq("verified", True)

            # Filtrar por ciudad si se especifica
            if city:
                query = query.ilike("city", f"%{city}%")

            # Construir filtro OR para búsqueda en profession y services
            or_conditions = []
            for token in tokens:
                token_lower = token.lower()
                or_conditions.append(f"profession.ilike.%{token_lower}%")
                or_conditions.append(f"services.ilike.%{token_lower}%")

            if or_conditions:
                query = query.or_(",".join(or_conditions))

            # Ordenar resultados
            query = query.order("rating", desc=True).order("created_at", desc=True)

            # Aplicar paginación
            query = query.range(request.offset, request.offset + request.limit - 1)

            # Ejecutar consulta (no bloquear loop)
            response = await self._run_supabase(lambda: query.execute(), label="providers.search_tokens")

            # Convertir resultados
            providers = []
            if response.data:
                for row in response.data:
                    providers.append(self._dict_to_provider_info_with_services(row))

            elapsed_ms = (perf_counter() - slow_start) * 1000
            if elapsed_ms >= SLOW_QUERY_THRESHOLD_MS:
                logger.info(
                    "perf_search_tokens",
                    extra={"elapsed_ms": round(elapsed_ms, 2), "limit": request.limit},
                )

            return providers

        except Exception as e:
            logger.error(f"Error en búsqueda por tokens: {e}")
            return []

    async def _search_fulltext(self, request: SearchRequest, query_analysis: Dict[str, Any]) -> List[ProviderInfo]:
        """Búsqueda full-text (para consultas complejas)"""
        try:
            slow_start = perf_counter()
            city = query_analysis.get("city")
            normalized_text = query_analysis["normalized_text"]

            if not self.supabase:
                raise Exception("Supabase client not initialized")

            # Para full-text search con Supabase, usamos textsearch en los campos
            # Convertimos la consulta a un array de palabras clave
            text_tokens = normalized_text.lower().split()

            # Construir consulta con Supabase
            query = self.supabase.table("providers").select("*", count="exact")

            # Filtrar por verified=true
            query = query.eq("verified", True)

            # Filtrar por ciudad si se especifica
            if city:
                query = query.ilike("city", f"%{city}%")

            # Construir filtro OR para búsqueda en profession y services usando todos los tokens
            or_conditions = []
            for token in text_tokens:
                if len(token) > 2:  # Ignorar tokens muy cortos
                    or_conditions.append(f"profession.ilike.%{token}%")
                    or_conditions.append(f"services.ilike.%{token}%")

            if or_conditions:
                query = query.or_(",".join(or_conditions))

            # Ordenar resultados
            query = query.order("rating", desc=True).order("created_at", desc=True)

            # Aplicar paginación
            query = query.range(request.offset, request.offset + request.limit - 1)

            # Ejecutar consulta (no bloquear loop)
            response = await self._run_supabase(lambda: query.execute(), label="providers.search_fulltext")

            # Convertir resultados
            providers = []
            if response.data:
                for row in response.data:
                    providers.append(self._dict_to_provider_info_with_services(row))

            elapsed_ms = (perf_counter() - slow_start) * 1000
            if elapsed_ms >= SLOW_QUERY_THRESHOLD_MS:
                logger.info(
                    "perf_search_fulltext",
                    extra={"elapsed_ms": round(elapsed_ms, 2), "limit": request.limit},
                )

            return providers

        except Exception as e:
            logger.error(f"Error en búsqueda full-text: {e}")
            return []

    async def _search_hybrid(self, request: SearchRequest, query_analysis: Dict[str, Any]) -> List[ProviderInfo]:
        """Búsqueda híbrida (combina múltiples estrategias)"""
        # Ejecutar búsquedas en paralelo
        token_task = self._search_by_tokens(request, query_analysis)
        fulltext_task = self._search_fulltext(request, query_analysis)

        try:
            token_results, fulltext_results = await asyncio.gather(token_task, fulltext_task, return_exceptions=True)

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

    async def _search_ai_enhanced(self, request: SearchRequest, query_analysis: Dict[str, Any]) -> List[ProviderInfo]:
        """Búsqueda mejorada con IA"""
        try:
            if not settings.openai_api_key:
                logger.warning("⚠️ OpenAI API key no configurada, fallback a búsqueda por tokens")
                return await self._search_by_tokens(request, query_analysis)

            # Mejorar consulta con IA
            enhanced_query = await self._enhance_query_with_ai(request.query, query_analysis)

            # Ejecutar búsqueda con consulta mejorada
            enhanced_analysis = analyze_query(enhanced_query)
            merged_tokens = list(
                {
                    *(query_analysis.get("tokens") or []),
                    *(enhanced_analysis.get("tokens") or []),
                }
            )
            merged_service_tokens = list(
                {
                    *(query_analysis.get("service_tokens") or []),
                    *(enhanced_analysis.get("service_tokens") or []),
                }
            )
            enhanced_analysis["tokens"] = merged_tokens
            enhanced_analysis["service_tokens"] = merged_service_tokens
            if query_analysis.get("city") and not enhanced_analysis.get("city"):
                enhanced_analysis["city"] = query_analysis["city"]
            return await self._search_by_tokens(request, enhanced_analysis)

        except Exception as e:
            logger.error(f"Error en búsqueda AI-enhanced: {e}")
            # Fallback a búsqueda por tokens
            return await self._search_by_tokens(request, query_analysis)

    async def _enhance_query_with_ai(self, original_query: str, analysis: Dict[str, Any]) -> str:
        """Mejorar consulta usando IA para máxima relevancia"""
        try:
            if not self.openai_client:
                logger.warning("⚠️ Cliente OpenAI no inicializado, fallback a búsqueda simple")
                return original_query

            system_prompt = """
            Eres un experto en servicios profesionales en Ecuador. Tu tarea es expandir
consultas de búsqueda para maximizar la relevancia con los proveedores disponibles.

            Reglas clave:
            1. Incluye sinónimos y términos relacionados comunes en Ecuador
            2. Convierte términos coloquiales a términos profesionales
            3. Incluye variaciones regionales de servicios
            4. Mantén el contexto original pero amplía la cobertura

            Ejemplos:
            - "limpieza facial" → "limpieza facial cuidado piel estética facial beautician cosmetología"
            - "necesito doctor" → "médico doctor consulta médica clínica salud"
            - "arreglo casa" → "albañil construcción reparación mantenimiento hogar"
            - "me corté el pelo" → "cortes de cabello peluquería barbería estilista"

            Responde ÚNICAMENTE con los términos de búsqueda mejorados, sin explicaciones.
            """

            async with self._openai_semaphore:
                response = await asyncio.wait_for(
                    self.openai_client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {
                                "role": "user",
                                "content": f"Expande esta consulta para encontrar mejores proveedores: {original_query}",
                            },
                        ],
                        max_tokens=80,
                        temperature=0.4,
                    ),
                    timeout=5,
                )

            enhanced_query = response.choices[0].message.content.strip()
            logger.info(f"🤖 IA Expandió: '{original_query}' → '{enhanced_query}'")
            return enhanced_query

        except Exception as e:
            logger.warning(f"⚠️ Error mejorando consulta con IA: {e}")
            return original_query

    def _load_intent_aliases(self) -> Dict[str, set[str]]:
        """Carga alias de intención desde archivo JSON (configurable)."""
        config_path = Path(__file__).resolve().parents[1] / "app" / "config" / "intent_aliases.json"
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
        except Exception as exc:  # pragma: no cover - logging auxiliar
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

        tokens_to_match = [token for token in tokens if (len(token) >= 4 or token in SERVICE_KEYWORDS)]

        if not tokens_to_match:
            # Si no quedan tokens útiles, evitar sobre-filtrar
            return providers

        filtered: List[ProviderInfo] = []
        for provider in providers:
            professions_text = " ".join(provider.professions or []).lower()
            services = " ".join(provider.services or []).lower()
            if any(token in professions_text or token in services for token in tokens_to_match):
                filtered.append(provider)
        return filtered

    async def _apply_filters(self, providers: List[ProviderInfo], filters: SearchFilters) -> List[ProviderInfo]:
        """Aplicar filtros adicionales a los resultados"""
        filtered_providers = []

        for provider in providers:
            # Filtro de verificación
            if filters.verified_only and not provider.verified:
                continue

            # Filtro de rating
            if provider.rating < filters.min_rating:
                continue

            # Filtro de ciudad (case-insensitive)
            if filters.city and provider.city.lower() != filters.city.lower():
                continue

            # Filtro de profesión
            if filters.profession:
                profession_lower = filters.profession.lower()
                if not any(profession_lower in p.lower() for p in provider.professions):
                    continue

            filtered_providers.append(provider)

        return filtered_providers

    def _sort_and_limit_results(self, providers: List[ProviderInfo], limit: int, offset: int) -> List[ProviderInfo]:
        """Ordenar y paginar resultados"""
        # Ordenar por rating (descendente) y fecha (más recientes primero)
        sorted_providers = sorted(providers, key=lambda p: (p.rating, p.created_at), reverse=True)

        # Aplicar paginación
        start_idx = offset
        end_idx = start_idx + limit
        return sorted_providers[start_idx:end_idx]

    def _calculate_overall_confidence(self, providers: List[ProviderInfo], query_analysis: Dict[str, Any]) -> float:
        """Calcular confianza general de los resultados"""
        if not providers:
            return 0.0

        # Factores de confianza
        avg_rating = sum(p.rating for p in providers) / len(providers)
        verified_ratio = sum(1 for p in providers if p.verified) / len(providers)

        # Ponderación (solo rating y verificación)
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

    def _row_to_provider_info(self, row) -> ProviderInfo:
        """Convertir fila de BD a ProviderInfo (para funciones antiguas)"""
        provider_data = row["provider_data"]

        return ProviderInfo(
            id=str(row["provider_id"]),
            phone_number=provider_data.get("phone_number", ""),
            full_name=provider_data.get("full_name", ""),
            city=provider_data.get("city"),
            rating=float(provider_data.get("rating", 0.0)),
            available=self._normalize_available(provider_data.get("available"), provider_data.get("verified")),
            verified=provider_data.get("verified", False),
            professions=provider_data.get("professions", []),
            services=provider_data.get("services", []),
            years_of_experience=provider_data.get("years_of_experience"),
            created_at=provider_data.get("created_at", datetime.now()),
            social_media_url=provider_data.get("social_media_url"),
            social_media_type=provider_data.get("social_media_type"),
            face_photo_url=provider_data.get("face_photo_url"),
        )

    def _row_to_provider_info_with_services(self, row) -> ProviderInfo:
        """Convertir fila de BD directa a ProviderInfo (para nuevas consultas)"""
        # Convertir services string a array si es necesario
        services_text = row.get("services", "")
        if isinstance(services_text, str):
            # Separar por | , ; u otros delimitadores comunes
            import re

            services = [s.strip() for s in re.split(r"[,|;]", services_text) if s.strip()]
        else:
            services = services_text or []

        return ProviderInfo(
            id=str(row["id"]),
            phone_number=row.get("phone", ""),
            full_name=row.get("full_name", ""),
            city=row.get("city"),
            rating=float(row.get("rating", 0.0)),
            available=self._normalize_available(row.get("available"), row.get("verified")),
            verified=row.get("verified", False),
            professions=[row.get("profession", "")] if row.get("profession") else [],
            services=services,
            years_of_experience=row.get("experience_years"),
            created_at=row.get("created_at", datetime.now()),
            social_media_url=row.get("social_media_url"),
            social_media_type=row.get("social_media_type"),
            face_photo_url=row.get("face_photo_url"),
        )

    def _dict_to_provider_info_with_services(self, row: Dict[str, Any]) -> ProviderInfo:
        """Convertir diccionario de Supabase a ProviderInfo"""
        # Convertir services string a array si es necesario
        services_text = row.get("services", "")
        if isinstance(services_text, str):
            # Separar por | , ; u otros delimitadores comunes
            import re

            services = [s.strip() for s in re.split(r"[,|;]", services_text) if s.strip()]
        else:
            services = services_text or []

        return ProviderInfo(
            id=str(row["id"]),
            phone_number=row.get("phone", ""),
            full_name=row.get("full_name", ""),
            city=row.get("city"),
            rating=float(row.get("rating", 0.0)),
            available=self._normalize_available(row.get("available"), row.get("verified")),
            verified=row.get("verified", False),
            professions=[row.get("profession", "")] if row.get("profession") else [],
            services=services,
            years_of_experience=row.get("experience_years"),
            created_at=row.get("created_at", datetime.now()),
            social_media_url=row.get("social_media_url"),
            social_media_type=row.get("social_media_type"),
            face_photo_url=row.get("face_photo_url"),
        )

    async def _update_metrics_async(self, request: SearchRequest, metadata: SearchMetadata, cache_hit: bool):
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
        """Verificar salud del servicio de búsqueda sin bloquear el loop"""
        health_info = {
            "database_connected": False,
            "redis_connected": await cache_service.health_check(),
            "search_service_ready": False,
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

        health_info["search_service_ready"] = health_info["database_connected"] and health_info["redis_connected"]

        return health_info


# Instancia global del servicio de búsqueda
search_service = SearchService()
