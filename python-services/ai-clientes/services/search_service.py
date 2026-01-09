"""
Servicio de búsqueda de proveedores para AI Clientes.

Este módulo contiene la lógica de búsqueda de proveedores, incluyendo:
- Búsqueda simple por profesión y ubicación
- Búsqueda inteligente con contexto
- Fallback a servicios legacy
- Extracción de profesión y ubicación desde texto
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import httpx
from shared_lib.config import settings
from shared_lib.service_catalog import COMMON_SERVICE_SYNONYMS, COMMON_SERVICES
from search_client import search_client
from utils.services_utils import (
    ECUADOR_CITY_SYNONYMS,
    _normalize_text_for_matching,
)

# Logger del módulo
logger = logging.getLogger(__name__)

# Config Proveedores service URL
PROVEEDORES_AI_SERVICE_URL = os.getenv(
    "PROVEEDORES_AI_SERVICE_URL",
    f"http://ai-proveedores:{settings.proveedores_service_port}",
)


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
# BÚSQUEDA INTELIGENTE
# ============================================================================

async def intelligent_search_providers_remote(
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Búsqueda inteligente de proveedores usando el nuevo Search Service
    """
    profession = payload.get("main_profession", "")
    location = payload.get("location", "")
    need_summary = payload.get("actual_need", "")

    # Construir query para Search Service
    if need_summary and need_summary != profession:
        query = f"{need_summary} {profession} en {location}"
    else:
        query = f"{profession} en {location}"

    logger.info("🔍 Buscando con Search Service: query='%s'", query)

    try:
        # Usar el nuevo Search Service
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
# BÚSQUEDA SIMPLE
# ============================================================================

async def search_providers(
    profession: str, location: str, radius_km: float = 10.0
) -> Dict[str, Any]:
    """
    Búsqueda de proveedores usando el nuevo Search Service
    """
    query = f"{profession} en {location}"
    logger.info(
        f"🔍 Búsqueda simple con Search Service: profession='{profession}', location='{location}'"
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

            # Fallback al método antiguo
            return await _fallback_search_providers_simple(
                profession, location, radius_km
            )

    except Exception as exc:
        logger.error(f"❌ Error en búsqueda simple Search Service: {exc}")

        # Fallback al método antiguo
        return await _fallback_search_providers_simple(profession, location, radius_km)


async def _fallback_search_providers_simple(
    profession: str, location: str, radius_km: float = 10.0
) -> Dict[str, Any]:
    """
    Fallback simple al método antiguo
    """
    url = f"{PROVEEDORES_AI_SERVICE_URL}/search-providers"
    payload = {"profession": profession, "location": location, "radius": radius_km}
    logger.info(
        f"🔄 Fallback simple a AI Proveedores: profession='{profession}', "
        f"location='{location}', radius={radius_km} -> {url}"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
        logger.info(f"⬅️ Respuesta de AI Proveedores status={resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            # Adapt to both possible response shapes
            providers = data.get("providers") or []
            providers = [
                provider for provider in providers if provider.get("verified", False)
            ]
            total = len(providers)
            logger.info(f"📦 Proveedores verificados tras fallback: total={total}")
            return {"ok": True, "providers": providers, "total": total}
        else:
            body_preview = None
            try:
                body_preview = resp.text[:300]
            except Exception:
                body_preview = "<no-body>"
            logger.warning(
                f"⚠️ AI Proveedores respondió {resp.status_code}: {body_preview}"
            )
            return {"ok": False, "providers": [], "total": 0}
    except Exception as e:
        logger.error(f"❌ Error llamando a AI Proveedores: {e}")
        return {"ok": False, "providers": [], "total": 0}
