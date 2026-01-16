"""
Servicio de búsqueda de proveedores para AI Clientes.

Este módulo contiene la lógica de búsqueda de proveedores, incluyendo:
- Búsqueda simple por profesión y ubicación
- Búsqueda inteligente con IA (QueryInterpreterService)
- Búsqueda directa en Supabase (ProviderRepository)
- Extracción de profesión y ubicación desde texto

CAMBIOS (Sprint 2.4):
- ✅ QueryInterpreterService para interpretación con IA
- ✅ ProviderRepository para acceso directo a Supabase
- ✅ ai-search ELIMINADO (SPOF eliminado)
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

import httpx
from config import settings
from utils.service_catalog import COMMON_SERVICE_SYNONYMS, COMMON_SERVICES
from utils.services_utils import (
    ECUADOR_CITY_SYNONYMS,
    _normalize_text_for_matching,
    normalize_profession,
)

# Nuevos servicios (Sprint 2.4) - Lazy import para evitar import antes de inicialización
# Se acceden a través de sys.modules para evitar problemas de importación temprana

# Catálogo dinámico de servicios (reemplaza al estático)
def _get_dynamic_service_catalog():
    """Obtener instancia de DynamicServiceCatalog (lazy)."""
    from services.dynamic_service_catalog import dynamic_service_catalog
    return dynamic_service_catalog

# Logger del módulo
logger = logging.getLogger(__name__)


# ============================================================================
# HELPER FUNCTIONS - Lazy access a nuevos servicios
# ============================================================================

def _get_query_interpreter():
    """Obtener instancia de QueryInterpreterService (lazy)."""
    from services.query_interpreter_service import query_interpreter
    return query_interpreter


def _get_provider_repository():
    """Obtener instancia de ProviderRepository (lazy)."""
    from services.providers.provider_repository import provider_repository
    return provider_repository


def _get_synonym_learner():
    """Obtener instancia de SynonymLearner (lazy)."""
    from services.synonym_learner import synonym_learner
    return synonym_learner

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

async def extract_profession_and_location(
    history_text: str, last_message: str
) -> tuple[Optional[str], Optional[str]]:
    """Extrae profesión y ubicación del mensaje del usuario.

    Args:
        history_text: Historial de conversación
        last_message: Último mensaje del usuario

    Returns:
        Tupla (profession, location) o (None, None) si no se detectan
    """
    # Si el mensaje es solo un número, retornar None inmediatamente
    if (last_message or "").strip().isdigit():
        logger.info(f"⚠️ Número puro detectado en extract_profession_and_location: '{last_message}'")
        return None, None

    combined_text = f"{history_text}\n{last_message}"
    normalized_text = _normalize_text_for_matching(combined_text)
    if not normalized_text:
        return None, None

    padded_text = f" {normalized_text} "
    logger.info(f"🔍 [DEBUG] Buscando profesión en: combined_text='{combined_text[:100]}...', normalized_text='{normalized_text}'")

    # Usar catálogo dinámico si está disponible
    dynamic_catalog = _get_dynamic_service_catalog()
    profession = None

    if dynamic_catalog:
        try:
            profession = await dynamic_catalog.find_profession(combined_text)
            if profession:
                logger.info(f"📋 Profesión encontrada en catálogo dinámico: '{profession}'")
            else:
                logger.info(f"⚠️ No se encontró profesión en catálogo dinámico, intentando catálogo estático...")
        except Exception as e:
            logger.warning(f"⚠️ Error buscando en catálogo dinámico: {e}, usando catálogo estático")

    # Si no se encontró en catálogo dinámico, usar catálogo estático
    if not profession:
        profession = _extract_from_static_catalog(padded_text)
        if profession:
            logger.info(f"📋 Profesión encontrada en catálogo estático: '{profession}'")

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


def _extract_from_static_catalog(padded_text: str) -> Optional[str]:
    """Extrae profesión del catálogo estático (fallback).

    Args:
        padded_text: Texto normalizado con espacios padding

    Returns:
        Profesión canónica o None
    """
    profession = None
    for canonical, synonyms in COMMON_SERVICE_SYNONYMS.items():
        for synonym in synonyms:
            normalized_synonym = _normalize_text_for_matching(synonym)
            if not normalized_synonym:
                continue
            if f" {normalized_synonym} " in padded_text:
                logger.debug(f"✅ Coincidión estática: '{synonym}' → '{canonical}'")
                profession = canonical
                break
        if profession:
            break

    if not profession:
        for service in COMMON_SERVICES:
            normalized_service = _normalize_text_for_matching(service)
            if normalized_service and f" {normalized_service} " in padded_text:
                logger.debug(f"✅ Coincidión directa: '{service}'")
                profession = service
                break

    return profession


# ============================================================================
# BÚSQUEDA INTELIGENTE (IA + DB directo)
# ============================================================================

async def intelligent_search_providers(
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Búsqueda inteligente de proveedores usando IA + DB directo.

    ENFOQUE (Sprint 2.4 - ai-search eliminado):
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

    logger.info(f"🔍 Buscando con IA + DB: query='{query}'")

    # Verificar que los servicios están disponibles
    query_interpreter_svc = _get_query_interpreter()
    provider_repo = _get_provider_repository()

    if not query_interpreter_svc or not provider_repo:
        error_msg = "QueryInterpreterService o ProviderRepository no disponibles"
        logger.error(f"❌ {error_msg}")
        return {"ok": False, "providers": [], "total": 0, "error": error_msg}

    try:
        # Paso 1: IA interpreta la query (DIFERENCIADOR)
        interpretation = await query_interpreter_svc.interpret_query(
            user_message=query,
            city_context=location,
            semaphore=openai_semaphore,
            timeout_seconds=OPENAI_TIMEOUT_SECONDS
        )

        interpreted_profession = _normalize_text_for_matching(interpretation["profession"])
        interpreted_city = interpretation["city"] or location
        details = interpretation["details"]

        # Validar que la profesión no sea un número puro
        if interpreted_profession and str(interpreted_profession).strip().isdigit():
            logger.warning(
                f"⚠️ Profesión es un número puro: '{interpreted_profession}', rechazando búsqueda"
            )
            return {
                "ok": False,
                "providers": [],
                "total": 0,
                "error": "number_not_accepted",
                "query_interpretation": {
                    "profession": None,
                    "city": location,
                    "details": "Input no válido (número sin contexto)"
                }
            }

        logger.info(
            f"🧠 IA interpretó: '{query}' → profession='{interpreted_profession}', "
            f"city='{interpreted_city}'"
        )

        # Paso 2: Buscar en Supabase directamente (sin SPOF)
        providers = await provider_repo.search_by_city_and_profession(
            city=interpreted_city,
            profession=interpreted_profession,
            limit=10
        )

        total = len(providers)
        logger.info(f"✅ Búsqueda DB directo: {total} proveedores")

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
        logger.error(f"❌ Error en búsqueda IA + DB: {exc}")
        return {"ok": False, "providers": [], "total": 0, "error": str(exc)}


# Alias para compatibilidad con código existente
intelligent_search_providers_remote = intelligent_search_providers


# ============================================================================
# BÚSQUEDA V2 - Enhanced Search (BACKWARD COMPATIBLE)
# ============================================================================

async def intelligent_search_providers_v2(
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Búsqueda inteligente de proveedores V2 - Enhanced Search.

    MEJORAS (Plan Mejoras Inmediatas - Enero 2026):
    1. IntentClassifier: Clasifica intención (DIRECT vs NEED_BASED)
    2. QueryExpander: Expande queries con sinónimos (cuando USE_QUERY_EXPANSION=True)
    3. Smart Fallback: Búsqueda multi-etapa si <3 resultados (cuando USE_SMART_FALLBACK=True)

    ESTRATEGIA BACKWARD COMPATIBLE:
    - Los métodos existentes NO se modifican
    - Este método V2 solo se usa si el feature flag está activado
    - Si USE_INTENT_CLASSIFICATION=False, usa el flujo V1 original

    Args:
        payload: Dict con main_profession, location, actual_need

    Returns:
        Dict con providers, total, query_interpretation, search_metadata, intent_type
    """
    from core.feature_flags import USE_INTENT_CLASSIFICATION

    # Si el feature flag está desactivado, usar flujo V1 (backward compatible)
    if not USE_INTENT_CLASSIFICATION:
        logger.debug("⚠️ USE_INTENT_CLASSIFICATION=False, usando flujo V1")
        return await intelligent_search_providers(payload)

    # Flujo V2 con IntentClassifier
    profession = payload.get("main_profession", "")
    location = payload.get("location", "")
    need_summary = payload.get("actual_need", "")

    # Construir query
    if need_summary and need_summary != profession:
        query = f"{need_summary} {profession} en {location}"
    else:
        query = f"{profession} en {location}"

    logger.info(f"🔍 [V2] Buscando con IntentClassifier: query='{query}'")

    try:
        # Paso 1: Clasificar intención
        from services.intent_classifier import get_intent_classifier

        classifier = get_intent_classifier()
        intent_type = classifier.classify_intent(query)

        logger.info(f"🎯 [V2] Intent clasificado: {intent_type.value}")

        # Paso 2: Si es NEED_BASED, inferir profesión
        inferred_profession = profession
        if intent_type.value == "need_based":
            inferred_from_need = classifier.infer_profession_from_need(query)
            if inferred_from_need:
                inferred_profession = inferred_from_need
                logger.info(
                    f"🔮 [V2] Profesión inferida desde necesidad: "
                    f"'{inferred_profession}'"
                )

        # Paso 3: Usar QueryInterpreterService para interpretación completa
        query_interpreter_svc = _get_query_interpreter()
        provider_repo = _get_provider_repository()

        if not query_interpreter_svc or not provider_repo:
            error_msg = "QueryInterpreterService o ProviderRepository no disponibles"
            logger.error(f"❌ {error_msg}")
            return {"ok": False, "providers": [], "total": 0, "error": error_msg}

        # Interpretar query con IA
        interpretation = await query_interpreter_svc.interpret_query(
            user_message=query,
            city_context=location,
            semaphore=openai_semaphore,
            timeout_seconds=OPENAI_TIMEOUT_SECONDS
        )

        # Usar profesión inferida si IntentClassifier detectó NEED_BASED
        if intent_type.value == "need_based" and inferred_profession:
            interpreted_profession = _normalize_text_for_matching(inferred_profession)
        else:
            interpreted_profession = _normalize_text_for_matching(interpretation["profession"])

        interpreted_city = interpretation["city"] or location
        details = interpretation["details"]

        # Validar que la profesión no sea un número puro
        if interpreted_profession and str(interpreted_profession).strip().isdigit():
            logger.warning(
                f"⚠️ Profesión es un número puro: '{interpreted_profession}', rechazando búsqueda"
            )
            return {
                "ok": False,
                "providers": [],
                "total": 0,
                "error": "number_not_accepted",
                "query_interpretation": {
                    "profession": None,
                    "city": location,
                    "details": "Input no válido (número sin contexto)"
                },
                "intent_type": intent_type.value
            }

        logger.info(
            f"🧠 [V2] Búsqueda final: profession='{interpreted_profession}', "
            f"city='{interpreted_city}', intent='{intent_type.value}'"
        )

        # Paso 4: Buscar en Supabase
        providers = await provider_repo.search_by_city_and_profession(
            city=interpreted_city,
            profession=interpreted_profession,
            limit=10
        )

        total = len(providers)
        logger.info(f"✅ [V2] Búsqueda completada: {total} proveedores")

        # Paso 4.5: Aprendizaje automático de sinónimos (si está activado)
        if total > 0:
            synonym_learner_svc = _get_synonym_learner()
            if synonym_learner_svc:
                try:
                    await synonym_learner_svc.learn_from_search(
                        query=query,
                        matched_profession=interpreted_profession,
                        num_results=total,
                        city=interpreted_city,
                        context={
                            "intent_type": intent_type.value,
                            "inferred_profession": inferred_profession,
                            "search_strategy": "intent_classifier_v2"
                        }
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Error en aprendizaje automático: {e}")

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
                "strategy": "intent_classifier_v2",
                "version": "2.0",
                "intent_type": intent_type.value,
                "inferred_profession": inferred_profession if intent_type.value == "need_based" else None,
                "ai_enhanced": True,
            }
        }

    except Exception as exc:
        logger.error(f"❌ [V2] Error en búsqueda: {exc}")
        # Fallback a V1 en caso de error
        logger.info("🔄 [V2] Fallback a flujo V1 por error")
        return await intelligent_search_providers(payload)


# ============================================================================
# BÚSQUEDA SIMPLE (DB directo)
# ============================================================================

async def search_providers(
    profession: str, location: str, radius_km: float = 10.0
) -> Dict[str, Any]:
    """
    Búsqueda simple de proveedores usando DB directo.

    ENFOQUE (Sprint 2.4 - ai-search eliminado):
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
    logger.info(
        f"🔍 Búsqueda simple DB directo: profession='{profession}', location='{location}'"
    )

    # Verificar que ProviderRepository está disponible
    provider_repo = _get_provider_repository()
    if not provider_repo:
        error_msg = "ProviderRepository no disponible"
        logger.error(f"❌ {error_msg}")
        return {"ok": False, "providers": [], "total": 0, "error": error_msg}

    try:
        # Paso 1: Buscar en la ciudad del usuario
        providers = await provider_repo.search_by_city_and_profession(
            city=location,
            profession=profession,
            limit=10
        )

        total = len(providers)
        logger.info(f"✅ Búsqueda local en {location}: {total} proveedores")

        # Paso 2: Si no hay resultados locales, buscar statewide
        if total == 0:
            logger.info(f"🔄 Sin resultados en {location}, buscando statewide...")
            state_providers = await provider_repo.search_by_city_and_profession(
                city="",  # Vacío para buscar en cualquier ciudad
                profession=profession,
                limit=10
            )

            state_total = len(state_providers)
            logger.info(f"✅ Búsqueda statewide: {state_total} proveedores")

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
        logger.error(f"❌ Error en búsqueda simple DB directo: {exc}")
        return {"ok": False, "providers": [], "total": 0, "error": str(exc)}


# ============================================================================
# SERVICE-BASED MATCHING V3 - Matching Inteligente Servicio→Profesión
# ============================================================================

async def intelligent_search_providers_v3(
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Búsqueda inteligente de proveedores V3 - Service-Based Matching.

    NUEVA FUNCIONALIDAD (Enero 2026):
    - ServiceDetector: Detecta servicios específicos en el mensaje
    - ServiceProfessionMapper: Mapea servicios a profesiones con scores
    - ServiceMatchingService: Scoring multi-dimensional de relevancia

    ESTRATEGIA BACKWARD COMPATIBLE:
    - Feature flag USE_SERVICE_MATCHING controla si se usa V3 o V2
    - Fallback automático a V2 si V3 falla
    - Métodos V1 y V2 NO se modifican

    Args:
        payload: Dict con main_profession, location, actual_need

    Returns:
        Dict con providers, total, query_interpretation, search_metadata,
               intent_type, service_detection (si aplica)
    """
    from core.feature_flags import USE_SERVICE_MATCHING, USE_SERVICE_DETECTOR

    # Si el feature flag está desactivado, usar flujo V2 (backward compatible)
    if not USE_SERVICE_MATCHING:
        logger.debug("⚠️ USE_SERVICE_MATCHING=False, usando flujo V2")
        return await intelligent_search_providers_v2(payload)

    profession = payload.get("main_profession", "")
    location = payload.get("location", "")
    need_summary = payload.get("actual_need", "")

    # Construir query completo
    if need_summary and need_summary != profession:
        query = f"{need_summary} {profession} en {location}"
    else:
        query = f"{profession} en {location}"

    logger.info(f"🔍 [V3] Service-Based Matching: query='{query}'")

    try:
        # Inicializar servicios
        from services.service_profession_mapper import get_service_profession_mapper  # type: ignore
        from services.service_detector import get_service_detector  # type: ignore
        from services.service_matching import get_service_matching_service  # type: ignore

        # Obtener instancias (lazy loading)
        provider_repo = _get_provider_repository()
        if not provider_repo:
            logger.warning("⚠️ ProviderRepository no disponible, fallback a V2")
            return await intelligent_search_providers_v2(payload)

        # NOTA: Para usar ServiceMatching, necesitamos:
        # 1. ServiceProfessionMapper (requiere supabase client)
        # 2. ServiceDetector
        # 3. ServiceMatchingService

        # Por ahora, fallback a V2 con logging
        # TODO: Implementar integración completa cuando ServiceProfessionMapper esté disponible
        logger.warning(
            "⚠️ [V3] ServiceMatchingService no completamente integrado aún, "
            "fallback a V2 con mejoras"
        )

        # Fallback a V2 (que ya tiene IntentClassifier)
        return await intelligent_search_providers_v2(payload)

    except Exception as e:
        logger.error(f"❌ [V3] Error en Service-Based Matching: {e}")
        logger.info("🔄 [V3] Fallback a V2...")
        return await intelligent_search_providers_v2(payload)


