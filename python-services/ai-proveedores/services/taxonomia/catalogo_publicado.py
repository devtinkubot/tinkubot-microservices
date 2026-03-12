"""Compatibilidad para leer la taxonomía publicada con caché opcional en Redis."""

from __future__ import annotations

import logging
import re
import unicodedata
from copy import deepcopy
from typing import Any, Dict, List, Optional

from config.configuracion import configuracion
from infrastructure.database import run_supabase

logger = logging.getLogger(__name__)

_CACHE_KEY_VERSION = "service-taxonomy:version"
_CACHE_KEY_PAYLOAD = "service-taxonomy:domains"
_PAYLOAD_VACIO: Dict[str, Any] = {
    "publication": None,
    "version": None,
    "domains": [],
}


async def obtener_taxonomia_publicada(
    supabase: Any,
    *,
    redis_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Devuelve la publicación activa/publicada y sus dominios con aliases/reglas."""
    payload_cache = await _leer_payload_cache(redis_client)
    if payload_cache is not None:
        return payload_cache

    publicacion = await _obtener_publicacion_actual(supabase)
    if publicacion is None:
        return deepcopy(_PAYLOAD_VACIO)

    dominios = await _obtener_dominios(supabase)
    aliases_por_dominio = await _obtener_aliases(supabase)
    canonicos_por_dominio = await _obtener_canonicos(supabase)
    reglas_por_dominio = await _obtener_reglas(supabase)

    payload = {
        "publication": publicacion,
        "version": publicacion.get("version"),
        "domains": [
            {
                **dominio,
                "aliases": aliases_por_dominio.get(dominio.get("id"), []),
                "canonical_services": canonicos_por_dominio.get(dominio.get("id"), []),
                "rules": reglas_por_dominio.get(dominio.get("id"), []),
            }
            for dominio in dominios
            if dominio.get("id") is not None
        ],
    }

    await _guardar_payload_cache(redis_client, payload)
    return payload


async def _leer_payload_cache(redis_client: Optional[Any]) -> Optional[Dict[str, Any]]:
    if redis_client is None:
        return None

    try:
        version = await redis_client.get(_CACHE_KEY_VERSION)
        payload = await redis_client.get(_CACHE_KEY_PAYLOAD)
    except Exception as exc:
        logger.warning("⚠️ No se pudo leer taxonomía desde Redis: %s", exc)
        return None

    if not isinstance(payload, dict):
        return None

    if payload.get("version") != version:
        return None

    if "publication" not in payload or "domains" not in payload:
        return None

    return deepcopy(payload)


async def _guardar_payload_cache(
    redis_client: Optional[Any],
    payload: Dict[str, Any],
) -> None:
    if redis_client is None:
        return

    ttl = getattr(
        configuracion,
        "taxonomy_cache_ttl_seconds",
        configuracion.ttl_cache_taxonomia_segundos,
    )
    try:
        await redis_client.set(_CACHE_KEY_VERSION, payload.get("version"), expire=ttl)
        await redis_client.set(_CACHE_KEY_PAYLOAD, deepcopy(payload), expire=ttl)
    except Exception as exc:
        logger.warning("⚠️ No se pudo guardar taxonomía en Redis: %s", exc)


async def _obtener_publicacion_actual(supabase: Any) -> Optional[Dict[str, Any]]:
    for status in ("active", "published"):
        respuesta = await run_supabase(
            lambda: supabase.table("service_taxonomy_publications")
            .select("id,version,status,published_by,published_at,notes")
            .eq("status", status)
            .order("published_at", desc=True)
            .limit(1)
            .execute(),
            label=f"service_taxonomy_publications.{status}",
        )
        filas = getattr(respuesta, "data", None) or []
        if filas:
            return filas[0]
    return None


async def _obtener_dominios(supabase: Any) -> List[Dict[str, Any]]:
    respuesta = await run_supabase(
        lambda: supabase.table("service_domains")
        .select("id,code,display_name,status,description,is_critical")
        .order("code", desc=False)
        .execute(),
        label="service_domains.catalog",
    )
    filas = getattr(respuesta, "data", None) or []
    return [fila for fila in filas if _fila_publicada(fila)]


async def _obtener_aliases(supabase: Any) -> Dict[Any, List[Dict[str, Any]]]:
    respuesta = await run_supabase(
        lambda: supabase.table("service_domain_aliases")
        .select(
            "id,domain_id,alias_text,alias_normalized,canonical_service_id,"
            "priority,status"
        )
        .order("priority", desc=False)
        .execute(),
        label="service_domain_aliases.catalog",
    )
    resultado: Dict[Any, List[Dict[str, Any]]] = {}
    for fila in getattr(respuesta, "data", None) or []:
        if not _fila_publicada(fila):
            continue
        domain_id = fila.get("domain_id")
        if domain_id is None:
            continue
        resultado.setdefault(domain_id, []).append(fila)
    return resultado


async def _obtener_canonicos(supabase: Any) -> Dict[Any, List[Dict[str, Any]]]:
    respuesta = await run_supabase(
        lambda: supabase.table("service_canonical_services")
        .select(
            "id,domain_id,canonical_name,canonical_normalized,description,"
            "metadata_json,status"
        )
        .order("canonical_normalized", desc=False)
        .execute(),
        label="service_canonical_services.catalog",
    )
    resultado: Dict[Any, List[Dict[str, Any]]] = {}
    for fila in getattr(respuesta, "data", None) or []:
        if not _fila_publicada(fila):
            continue
        domain_id = fila.get("domain_id")
        if domain_id is None:
            continue
        resultado.setdefault(domain_id, []).append(fila)
    return resultado


async def _obtener_reglas(supabase: Any) -> Dict[Any, List[Dict[str, Any]]]:
    respuesta = await run_supabase(
        lambda: supabase.table("service_precision_rules")
        .select(
            "id,domain_id,required_dimensions,generic_examples,"
            "sufficient_examples,client_prompt_template,provider_prompt_template"
        )
        .execute(),
        label="service_precision_rules.catalog",
    )
    resultado: Dict[Any, List[Dict[str, Any]]] = {}
    for fila in getattr(respuesta, "data", None) or []:
        if not _fila_publicada(fila):
            continue
        domain_id = fila.get("domain_id")
        if domain_id is None:
            continue
        resultado.setdefault(domain_id, []).append(fila)
    return resultado


def _fila_publicada(fila: Dict[str, Any]) -> bool:
    status = fila.get("status")
    if status is None:
        return fila.get("is_active", True) is True
    return status in {"active", "published"}


def resolver_servicio_canonico_publicado(
    servicio: Optional[str],
    taxonomia: Optional[Dict[str, Any]],
) -> Optional[str]:
    servicio_normalizado = _normalizar_servicio(servicio or "")
    if not servicio_normalizado or not isinstance(taxonomia, dict):
        return None

    for dominio in taxonomia.get("domains") or []:
        canonicos_por_id = {
            str(canonico.get("id")): str(canonico.get("canonical_name") or "").strip()
            for canonico in (dominio.get("canonical_services") or [])
            if canonico.get("id") and str(canonico.get("canonical_name") or "").strip()
        }

        for canonico in dominio.get("canonical_services") or []:
            canonico_normalizado = _normalizar_servicio(
                canonico.get("canonical_normalized") or canonico.get("canonical_name") or ""
            )
            if canonico_normalizado == servicio_normalizado:
                nombre = str(canonico.get("canonical_name") or "").strip()
                return nombre or None

        for alias in dominio.get("aliases") or []:
            alias_normalizado = _normalizar_servicio(
                alias.get("alias_normalized") or alias.get("alias_text") or ""
            )
            if alias_normalizado != servicio_normalizado:
                continue
            canonical_service_id = alias.get("canonical_service_id")
            if canonical_service_id:
                canonical_name = canonicos_por_id.get(str(canonical_service_id))
                if canonical_name:
                    return canonical_name
    return None


def _normalizar_servicio(texto: str) -> str:
    base = unicodedata.normalize("NFD", (texto or "").strip().lower())
    sin_acentos = "".join(ch for ch in base if unicodedata.category(ch) != "Mn")
    limpio = re.sub(r"[^a-z0-9\s]", " ", sin_acentos)
    return re.sub(r"\s+", " ", limpio).strip()
