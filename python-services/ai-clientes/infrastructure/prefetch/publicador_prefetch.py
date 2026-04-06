"""Publicador de eventos de prefetch de búsqueda a Redis Streams."""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)

PREFETCH_STREAM_KEY = "client_search_prefetch_events"
PREFETCH_CACHE_KEY_PREFIX = "prefetch:search:"


def _calcular_fingerprint(servicio: str, ciudad: str) -> str:
    """Genera un fingerprint determinista para servicio + ciudad."""
    texto = f"{servicio.strip().lower()}|{ciudad.strip().lower()}"
    return hashlib.sha256(texto.encode()).hexdigest()[:16]


async def publicar_prefetch_busqueda(
    telefono: str,
    flujo: Dict[str, Any],
    redis_client: Any,
) -> bool:
    """Publica evento de prefetch al Redis Stream. Fire-and-forget.

    Args:
        telefono: Número de teléfono del cliente.
        flujo: Diccionario con el estado del flujo (debe tener service_candidate, city).
        redis_client: Instancia de ClienteRedis conectada.

    Returns:
        True si se publicó, False si no (nunca lanza excepción).
    """
    try:
        if not redis_client or not redis_client.redis_client:
            logger.warning("prefetch: Redis no disponible, omitiendo")
            return False

        servicio = (flujo.get("service_candidate") or "").strip()
        ciudad = (flujo.get("city") or "").strip()

        if not servicio or not ciudad:
            logger.debug("prefetch: sin servicio o ciudad, omitiendo")
            return False

        fingerprint = _calcular_fingerprint(servicio, ciudad)
        idempotency_key = hashlib.sha256(
            f"{telefono}:{fingerprint}:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}".encode()
        ).hexdigest()[:20]

        payload = {
            "normalized_service": servicio,
            "service_summary": (flujo.get("service_summary") or servicio),
            "domain": flujo.get("service_domain") or "",
            "domain_code": flujo.get("service_domain_code") or "",
            "category": flujo.get("service_category") or "",
            "category_name": flujo.get("service_category_name") or "",
            "city": ciudad,
            "raw_input": flujo.get("descripcion_problema") or servicio,
            "search_fingerprint": fingerprint,
        }

        await redis_client.redis_client.xadd(
            PREFETCH_STREAM_KEY,
            {
                "event_type": "client.search.prefetch_requested",
                "phone": telefono,
                "idempotency_key": idempotency_key,
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "payload": json.dumps(payload),
            },
        )

        logger.info(
            "prefetch: evento publicado phone=%s service='%s' city='%s'",
            telefono,
            servicio[:40],
            ciudad,
        )
        return True

    except Exception as exc:
        logger.warning("prefetch: error publicando evento: %s", exc)
        return False


async def obtener_prefetch_cache(
    telefono: str,
    servicio: str,
    ciudad: str,
    redis_client: Any,
) -> Dict[str, Any] | None:
    """Lee resultados pre-fetched de Redis si están disponibles y el fingerprint coincide.

    Args:
        telefono: Número de teléfono del cliente.
        servicio: Servicio normalizado.
        ciudad: Ciudad de búsqueda.
        redis_client: Instancia de ClienteRedis conectada.

    Returns:
        Dict con providers y metadata si hay cache hit, None si no.
    """
    try:
        if not redis_client or not redis_client.redis_client:
            return None

        key = f"{PREFETCH_CACHE_KEY_PREFIX}{telefono}"
        raw = await redis_client.redis_client.get(key)
        if not raw:
            return None

        cached = json.loads(raw)
        fingerprint_esperado = _calcular_fingerprint(servicio, ciudad)

        if cached.get("search_fingerprint") != fingerprint_esperado:
            logger.info("prefetch: fingerprint mismatch, descartando cache phone=%s", telefono)
            return None

        # Consumir cache (uso único)
        await redis_client.redis_client.delete(key)

        logger.info(
            "prefetch: cache hit phone=%s providers=%d",
            telefono,
            len(cached.get("providers") or []),
        )
        return cached

    except Exception as exc:
        logger.warning("prefetch: error leyendo cache: %s", exc)
        return None
