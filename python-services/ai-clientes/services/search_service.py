"""
Servicio de búsqueda de proveedores para AI Clientes.

Este módulo contiene la lógica de búsqueda de proveedores, incluyendo:
- Búsqueda simple por profesión y ubicación
- Búsqueda inteligente con IA (QueryInterpreterService)
- Búsqueda directa en Supabase (ProviderRepository)
- Fallback a ai-search (search_client) para compatibilidad
- Extracción de profesión y ubicación desde texto

CAMBIOS (Sprint 2.4):
- Añadido QueryInterpreterService para interpretación con IA
- Añadido ProviderRepository para acceso directo a Supabase
- Mantenido fallback a search_client para evitar breaking changes
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

import httpx
from config import settings
from utils.service_catalog import COMMON_SERVICE_SYNONYMS, COMMON_SERVICES
from search_client import search_client
from utils.services_utils import (
    ECUADOR_CITY_SYNONYMS,
    _normalize_text_for_matching,
)

# Nuevos servicios (Sprint 2.4)
from query_interpreter_service import query_interpreter
from providers.provider_repository import provider_repository

# Logger del módulo
logger = logging.getLogger(__name__)

# Config Proveedores service URL
PROVEEDORES_AI_SERVICE_URL = os.getenv(
    "PROVEEDORES_AI_SERVICE_URL",
    f"http://ai-proveedores:{settings.proveedores_service_port}",
)

# Configuración OpenAI para interpretación de queries
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "5"))
MAX_OPENAI_CONCURRENCY = int(os.getenv("MAX_OPENAI_CONCURRENCY", "5"))
openai_semaphore: Optional[asyncio.Semaphore] = None


def initialize_openai_semaphore() -> None:
    """Inicializa el semáforo de OpenAI."""
    global openai_semaphore
    openai_semaphore = asyncio.Semaphore(MAX_OPENAI_CONCURRENCY)
    logger.info(f"✅ OpenAI semaphore inicializado (concurrency: {MAX_OPENAI_CONCURRENCY})")


# ============================================================================
# EXTRACCIÓN DE ENTIDADES
# ============================================================================

def extract_profession_and_location(
    history_text: str, last_message: str
) -> tuple[Optional[str], Optional[str]]:
    """Extrae profesión y ubicación del mensaje del usuario.

    Args:
        history_text: Historial de conversación
        last_message: Último mensaje del usuario

    Returns:
        Tupla (profession, location) o (None, None) si no se detectan
    """
    combined_text = f"{history_text}\n{last_message}"
    normalized_text = _normalize_text_for_matching(combined_text)
    if not normalized_text:
        return None, None

    padded_text = f" {normalized_text} "

    profession = None
    for canonical, synonyms in COMMON_SERVICE_SYNONYMS.items():
        for synonym in synonyms:
            normalized_synonym = _normalize_text_for_matching(synonym)
            if not normalized_synonym:
                continue
            if f" {normalized_synonym} " in padded_text:
                profession = canonical
                break
        if profession:
            break

    if not profession:
        for service in COMMON_SERVICES:
            normalized_service = _normalize_text_for_matching(service)
            if normalized_service and f" {normalized_service} " in padded_text:
                profession = service
                break

    location = None
    for canonical_city, synonyms in ECUADOR_CITY_SYNONYMS.items():
        for synonym in synonyms:
            normalized_synonym = _normalize_text_for_matching(synonym)
            if not normalized_synonym:
                continue
            if f" {normalized_synonym} " in padded_text:
                location = canonical_city
                break
        if location:
            break

    return profession, location


# ============================================================================
# BÚSQUEDA INTELIGENTE (NUEVO: IA + DB directo)
# ============================================================================

async def intelligent_search_providers_new(
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Búsqueda inteligente de proveedores usando IA + DB directo.

    NUEVO ENFOQUE (Sprint 2.4):
    1. QueryInterpreterService interpreta la query con IA
    2. ProviderRepository busca directamente en Supabase
    3. Sin dependencia de ai-search (SPOF eliminado)

    Args:
        payload: Dict con main_profession, location, actual_need

    Returns:
        Dict con providers, total, query_interpretation, search_metadata
    """
    profession = payload.get("main_profession", "")
    location = payload.get("location", "")
    need_summary = payload.get("actual_need", "")

    # Construir query para IA
    if need_summary and need_summary != profession:
        query = f"{need_summary} {profession} en {location}"
    else:
        query = f"{profession} en {location}"

    logger.info(f"🔍 [NUEVO] Buscando con IA + DB: query='{query}'")

    # Verificar que los nuevos servicios están disponibles
    if not query_interpreter or not provider_repository:
        logger.warning("⚠️ Nuevos servicios no disponibles, usando fallback")
        return await _intelligent_search_fallback(payload)

    try:
        # Paso 1: IA interpreta la query (DIFERENCIADOR)
        interpretation = await query_interpreter.interpret_query(
            user_message=query,
            city_context=location,
            semaphore=openai_semaphore,
            timeout_seconds=OPENAI_TIMEOUT_SECONDS
        )

        interpreted_profession = interpretation["profession"]
        interpreted_city = interpretation["city"] or location
        details = interpretation["details"]

        logger.info(
            f"🧠 IA interpretó: '{query}' → profession='{interpreted_profession}', "
            f"city='{interpreted_city}'"
        )

        # Paso 2: Buscar en Supabase directamente (sin SPOF)
        providers = await provider_repository.search_by_city_and_profession(
            city=interpreted_city,
            profession=interpreted_profession,
            limit=10
        )

        total = len(providers)
        logger.info(f"✅ [NUEVO] Búsqueda DB directo: {total} proveedores")

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
                "strategy": "ai_interpretation_db_search",
                "ai_enhanced": True,
                "search_time_ms": 150  # ~100ms IA + ~50ms DB
            }
        }

    except Exception as exc:
        logger.error(f"❌ [NUEVO] Error en búsqueda IA + DB: {exc}")
        # Fallback al método antiguo
        return await _intelligent_search_fallback(payload)


async def _intelligent_search_fallback(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback a ai-search (search_client) para compatibilidad."""
    return await intelligent_search_providers_legacy(payload)


async def intelligent_search_providers_remote(
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Búsqueda inteligente de proveedores ( enruta a nuevo o legacy).

    PRIORIDAD: Nuevo enfoque (IA + DB) → Fallback a ai-search
    """
    # Intentar nuevo enfoque primero
    try:
        result = await intelligent_search_providers_new(payload)
        if result.get("ok") and result.get("total", 0) > 0:
            return result
    except Exception as e:
        logger.warning(f"⚠️ Nuevo enfoque falló, usando fallback: {e}")

    # Fallback al método legacy (ai-search)
    return await intelligent_search_providers_legacy(payload)


async def intelligent_search_providers_legacy(
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Búsqueda inteligente LEGACY (usa ai-search via search_client).

    MANTENIDO para compatibilidad y fallback.
    """
    profession = payload.get("main_profession", "")
    location = payload.get("location", "")
    need_summary = payload.get("actual_need", "")

    # Construir query para Search Service
    if need_summary and need_summary != profession:
        query = f"{need_summary} {profession} en {location}"
    else:
        query = f"{profession} en {location}"

    logger.info(f"🔍 [LEGACY] Buscando con ai-search: query='{query}'")

    try:
        # Usar ai-search vía search_client
        result = await search_client.search_providers(
            query=query,
            city=location,
            limit=10,
            use_ai_enhancement=True,
        )

        if result.get("ok"):
            providers = result.get("providers", [])
            total = result.get("total", len(providers))

            # Log de metadatos de búsqueda
            metadata = result.get("search_metadata", {})
            logger.info(
                f"✅ Búsqueda Search Service exitosa: {total} proveedores "
                f"(estrategia: {metadata.get('strategy')}, "
                f"tiempo: {metadata.get('search_time_ms')}ms, "
                f"IA: {metadata.get('used_ai_enhancement')})"
            )

            return {"ok": True, "providers": providers, "total": total}
        else:
            error = result.get("error", "Error desconocido")
            logger.warning(f"⚠️ Search Service falló: {error}")

            # Fallback al método antiguo
            return await _fallback_search_providers_remote(payload)

    except Exception as exc:
        logger.error(f"❌ Error en Search Service: {exc}")

        # Fallback al método antiguo
        return await _fallback_search_providers_remote(payload)


async def _fallback_search_providers_remote(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fallback al método antiguo de búsqueda (ai-service-proveedores)
    """
    url = f"{PROVEEDORES_AI_SERVICE_URL}/intelligent-search"
    logger.info("🔄 Fallback a búsqueda antigua -> %s payload=%s", url, payload)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code == 200:
            data = resp.json()
            providers = data.get("providers") or []
            providers = [
                provider for provider in providers if provider.get("verified", False)
            ]
            total = len(providers)
            logger.info("📦 Fallback inteligente filtró %s proveedores verificados", total)
            return {"ok": True, "providers": providers, "total": total}
        logger.warning(
            "⚠️ Respuesta no exitosa en búsqueda inteligente %s cuerpo=%s",
            resp.status_code,
            resp.text[:300] if hasattr(resp, "text") else "<sin cuerpo>",
        )
        return {"ok": False, "providers": [], "total": 0}
    except Exception as exc:
        logger.error("❌ Error en fallback search: %s", exc)
        return {"ok": False, "providers": [], "total": 0}


# ============================================================================
# BÚSQUEDA SIMPLE (NUEVO: DB directo + Fallback)
# ============================================================================

async def search_providers_new(
    profession: str, location: str, radius_km: float = 10.0
) -> Dict[str, Any]:
    """
    Búsqueda simple de proveedores usando DB directo.

    NUEVO ENFOQUE (Sprint 2.4):
    1. ProviderRepository busca directamente en Supabase
    2. Sin dependencia de ai-search (SPOF eliminado)
    3. Mantiene lógica statewide si no hay resultados locales

    Args:
        profession: Profesión a buscar
        location: Ciudad del usuario
        radius_km: Radio de búsqueda (no usado en DB directo)

    Returns:
        Dict con providers, total, search_scope
    """
    query = f"{profession} en {location}"
    logger.info(
        f"🔍 [NUEVO] Búsqueda simple DB directo: profession='{profession}', location='{location}'"
    )

    # Verificar que ProviderRepository está disponible
    if not provider_repository:
        logger.warning("⚠️ ProviderRepository no disponible, usando fallback")
        return await search_providers_legacy(profession, location, radius_km)

    try:
        # Paso 1: Buscar en la ciudad del usuario
        providers = await provider_repository.search_by_city_and_profession(
            city=location,
            profession=profession,
            limit=10
        )

        total = len(providers)
        logger.info(f"✅ [NUEVO] Búsqueda local en {location}: {total} proveedores")

        # Paso 2: Si no hay resultados locales, buscar statewide
        if total == 0:
            logger.info(f"🔄 Sin resultados en {location}, buscando statewide...")
            state_providers = await provider_repository.search_by_city_and_profession(
                city="",  # Vacío para buscar en cualquier ciudad
                profession=profession,
                limit=10
            )

            state_total = len(state_providers)
            logger.info(f"✅ [NUEVO] Búsqueda statewide: {state_total} proveedores")

            if state_total > 0:
                # Agregar información de ubicación a cada proveedor
                for provider in state_providers:
                    provider['is_statewide'] = True
                    provider['search_scope'] = 'statewide'
                    provider['user_city'] = location

                return {
                    "ok": True,
                    "providers": state_providers,
                    "total": state_total,
                    "search_scope": "statewide",
                    "note": f"No hay proveedores en {location}, pero encontramos {state_total} proveedores disponibles en otras ciudades."
                }

        return {
            "ok": True,
            "providers": providers,
            "total": total,
            "search_scope": "local"
        }

    except Exception as exc:
        logger.error(f"❌ [NUEVO] Error en búsqueda simple DB directo: {exc}")
        # Fallback al método legacy
        return await search_providers_legacy(profession, location, radius_km)


async def search_providers_legacy(
    profession: str, location: str, radius_km: float = 10.0
) -> Dict[str, Any]:
    """
    Búsqueda simple LEGACY (usa ai-search via search_client).

    MANTENIDO para compatibilidad y fallback.
    """
    query = f"{profession} en {location}"
    logger.info(
        f"🔍 [LEGACY] Búsqueda simple ai-search: profession='{profession}', location='{location}'"
    )

    try:
        # Primera búsqueda: en la ciudad del usuario
        result = await search_client.search_providers(
            query=query,
            city=location,
            limit=10,
            use_ai_enhancement=True,  # Búsqueda AI-first optimizada
        )

        if result.get("ok"):
            providers = result.get("providers", [])
            total = result.get("total", len(providers))

            # Log de metadatos
            metadata = result.get("search_metadata", {})
            logger.info(
                f"✅ Búsqueda local en {location}: {total} proveedores "
                f"(estrategia: {metadata.get('strategy')}, "
                f"tiempo: {metadata.get('search_time_ms')}ms)"
            )

            # Si no hay resultados locales, buscar statewide
            if total == 0:
                logger.info(f"🔄 Sin resultados en {location}, buscando statewide...")
                state_result = await search_client.search_providers(
                    query=profession,  # Query sin restricción de ciudad
                    limit=10,
                    use_ai_enhancement=True,
                )

                if state_result.get("ok"):
                    state_providers = state_result.get("providers", [])
                    state_total = state_result.get("total", len(state_providers))

                    state_metadata = state_result.get("search_metadata", {})
                    logger.info(
                        f"✅ Búsqueda statewide: {state_total} proveedores "
                        f"(estrategia: {state_metadata.get('strategy')}, "
                        f"tiempo: {state_metadata.get('search_time_ms')}ms)"
                    )

                    if state_total > 0:
                        # Agregar información de ubicación a cada proveedor
                        for provider in state_providers:
                            provider['is_statewide'] = True
                            provider['search_scope'] = 'statewide'
                            provider['user_city'] = location

                        return {
                            "ok": True,
                            "providers": state_providers,
                            "total": state_total,
                            "search_scope": "statewide",
                            "note": f"No hay proveedores en {location}, pero encontramos {state_total} proveedores disponibles en otras ciudades."
                        }

            return {
                "ok": True,
                "providers": providers,
                "total": total,
                "search_scope": "local"
            }
        else:
            error = result.get("error", "Error desconocido")
            logger.warning(f"⚠️ Search Service simple falló: {error}")

            # Fallback eliminado: endpoint /search-providers ya no existe
            logger.error(f"❌ No hay fallback disponible (endpoint /search-providers eliminado)")
            return {
                "ok": False,
                "providers": [],
                "total": 0,
                "error": "Search Service falló y no hay fallback disponible"
            }

    except Exception as exc:
        logger.error(f"❌ Error en búsqueda simple Search Service: {exc}")

        # Fallback eliminado: endpoint /search-providers ya no existe
        logger.error(f"❌ No hay fallback disponible (endpoint /search-providers eliminado)")
        return {
            "ok": False,
            "providers": [],
            "total": 0,
            "error": f"Error en búsqueda: {str(exc)}"
        }


# ============================================================================
# ENRUTAMIENTO PRINCIPAL (Nuevo → Legacy)
# ============================================================================

async def search_providers(
    profession: str, location: str, radius_km: float = 10.0
) -> Dict[str, Any]:
    """
    Búsqueda de proveedores (enruta a nuevo o legacy).

    PRIORIDAD: Nuevo enfoque (DB directo) → Fallback a ai-search

    Esta función mantiene compatibilidad con el código existente
    mientras implementa el nuevo enfoque sin SPOF.

    Args:
        profession: Profesión a buscar
        location: Ciudad del usuario
        radius_km: Radio de búsqueda (no usado en DB directo)

    Returns:
        Dict con providers, total, search_scope
    """
    # Intentar nuevo enfoque primero
    try:
        result = await search_providers_new(profession, location, radius_km)
        if result.get("ok"):
            return result
    except Exception as e:
        logger.warning(f"⚠️ Nuevo enfoque simple falló, usando fallback: {e}")

    # Fallback al método legacy (ai-search)
    return await search_providers_legacy(profession, location, radius_km)
