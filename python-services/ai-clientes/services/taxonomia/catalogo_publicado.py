import logging
import re
import unicodedata
from collections import defaultdict
from typing import Any, Dict, Optional

from config.configuracion import configuracion
from infrastructure.database import run_supabase

logger = logging.getLogger(__name__)

_CACHE_VERSION_KEY = "service-taxonomy:version"
_CACHE_DOMAINS_KEY = "service-taxonomy:domains"
_STATUSES_PUBLICADOS = {"published", "active"}


async def obtener_taxonomia_publicada(
    supabase: Any,
    redis_client: Any = None,
    force_refresh: bool = False,
) -> Optional[Dict[str, Any]]:
    if not force_refresh:
        cache = await _leer_cache(redis_client)
        if cache:
            return cache

    if not supabase:
        return None

    publicacion = await _obtener_publicacion(supabase)
    if not publicacion:
        return None

    dominios = await _obtener_dominios(supabase)
    aliases = await _obtener_aliases(supabase)
    canonicos = await _obtener_canonicos(supabase)
    reglas = await _obtener_reglas(supabase)
    payload = _construir_payload(publicacion, dominios, aliases, canonicos, reglas)

    await _guardar_cache(redis_client, payload)
    return payload


async def _leer_cache(redis_client: Any) -> Optional[Dict[str, Any]]:
    if not redis_client:
        return None

    try:
        version = await redis_client.get(_CACHE_VERSION_KEY)
        payload = await redis_client.get(_CACHE_DOMAINS_KEY)
    except Exception as exc:
        logger.warning("taxonomy_cache_read_failed: %s", exc)
        return None

    if not version or not isinstance(payload, dict):
        return None
    if payload.get("version") != version:
        return None
    return payload


async def _guardar_cache(redis_client: Any, payload: Dict[str, Any]) -> None:
    if not redis_client:
        return

    ttl = configuracion.taxonomy_cache_ttl_seconds
    try:
        await redis_client.set(_CACHE_VERSION_KEY, payload["version"], expire=ttl)
        await redis_client.set(_CACHE_DOMAINS_KEY, payload, expire=ttl)
    except Exception as exc:
        logger.warning("taxonomy_cache_write_failed: %s", exc)


async def _obtener_publicacion(supabase: Any) -> Optional[Dict[str, Any]]:
    respuesta = await run_supabase(
        lambda: supabase.table("service_taxonomy_publications")
        .select("*")
        .order("version", desc=True)
        .limit(10)
        .execute(),
        etiqueta="taxonomy.publication",
    )
    data = getattr(respuesta, "data", None) or []
    for fila in data:
        if str(fila.get("status") or "").strip().lower() in _STATUSES_PUBLICADOS:
            return fila
    return None


async def _obtener_dominios(supabase: Any) -> list[Dict[str, Any]]:
    respuesta = await run_supabase(
        lambda: supabase.table("service_domains")
        .select("*")
        .order("code")
        .execute(),
        etiqueta="taxonomy.domains",
    )
    return [
        fila
        for fila in (getattr(respuesta, "data", None) or [])
        if str(fila.get("status") or "").strip().lower() in _STATUSES_PUBLICADOS
    ]


async def _obtener_aliases(supabase: Any) -> list[Dict[str, Any]]:
    respuesta = await run_supabase(
        lambda: supabase.table("service_domain_aliases")
        .select("*")
        .order("alias_normalized")
        .execute(),
        etiqueta="taxonomy.aliases",
    )
    return [fila for fila in (getattr(respuesta, "data", None) or []) if _alias_activo(fila)]


async def _obtener_canonicos(supabase: Any) -> list[Dict[str, Any]]:
    respuesta = await run_supabase(
        lambda: supabase.table("service_canonical_services")
        .select("*")
        .order("canonical_normalized")
        .execute(),
        etiqueta="taxonomy.canonical_services",
    )
    return [fila for fila in (getattr(respuesta, "data", None) or []) if _alias_activo(fila)]


async def _obtener_reglas(supabase: Any) -> list[Dict[str, Any]]:
    respuesta = await run_supabase(
        lambda: supabase.table("service_precision_rules")
        .select("*")
        .order("domain_id")
        .execute(),
        etiqueta="taxonomy.rules",
    )
    return getattr(respuesta, "data", None) or []


def _construir_payload(
    publicacion: Dict[str, Any],
    dominios: list[Dict[str, Any]],
    aliases: list[Dict[str, Any]],
    canonicos: list[Dict[str, Any]],
    reglas: list[Dict[str, Any]],
) -> Dict[str, Any]:
    aliases_por_dominio: dict[str, list[Dict[str, Any]]] = defaultdict(list)
    for alias in aliases:
        domain_id = alias.get("domain_id")
        if domain_id:
            aliases_por_dominio[str(domain_id)].append(alias)

    canonicos_por_dominio: dict[str, list[Dict[str, Any]]] = defaultdict(list)
    for canonico in canonicos:
        domain_id = canonico.get("domain_id")
        if domain_id:
            canonicos_por_dominio[str(domain_id)].append(canonico)

    reglas_por_dominio = {
        str(regla.get("domain_id")): regla for regla in reglas if regla.get("domain_id")
    }

    dominios_payload = []
    for dominio in dominios:
        domain_id = str(dominio.get("id"))
        aliases_dominio = aliases_por_dominio.get(domain_id, [])
        regla = reglas_por_dominio.get(domain_id)
        dominios_payload.append(
            {
                **dominio,
                "aliases": aliases_dominio,
                "canonical_services": canonicos_por_dominio.get(domain_id, []),
                "precision_rule": regla,
            }
        )

    return {
        "version": publicacion.get("version"),
        "publication": publicacion,
        "domains": dominios_payload,
    }


def construir_mapa_servicios_genericos(
    taxonomia: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    if not isinstance(taxonomia, dict):
        return {}

    mapa: Dict[str, str] = {}
    for dominio in taxonomia.get("domains") or []:
        codigo = str(dominio.get("code") or "").strip().lower()
        if not codigo:
            continue

        for alias in dominio.get("aliases") or []:
            alias_normalizado = _normalizar_servicio(alias.get("alias_normalized") or "")
            if alias_normalizado:
                mapa[alias_normalizado] = codigo

        regla = dominio.get("precision_rule")
        if isinstance(regla, dict):
            for ejemplo in regla.get("generic_examples") or []:
                ejemplo_normalizado = _normalizar_servicio(ejemplo or "")
                if ejemplo_normalizado:
                    mapa[ejemplo_normalizado] = codigo

    return mapa


def detectar_servicio_canonico_en_taxonomia(
    servicio: Optional[str],
    taxonomia: Optional[Dict[str, Any]],
) -> Optional[Dict[str, str]]:
    servicio_normalizado = _normalizar_servicio(servicio or "")
    if not servicio_normalizado or not isinstance(taxonomia, dict):
        return None

    for dominio in taxonomia.get("domains") or []:
        codigo = str(dominio.get("code") or "").strip().lower()
        if not codigo:
            continue
        for canonico in dominio.get("canonical_services") or []:
            canonico_normalizado = _normalizar_servicio(
                canonico.get("canonical_normalized") or canonico.get("canonical_name") or ""
            )
            if canonico_normalizado != servicio_normalizado:
                continue
            return {
                "domain_code": codigo,
                "canonical_name": str(canonico.get("canonical_name") or "").strip(),
                "canonical_normalized": canonico_normalizado,
            }
    return None


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


def detectar_dominio_generico_en_taxonomia(
    servicio: Optional[str],
    taxonomia: Optional[Dict[str, Any]],
) -> Optional[str]:
    servicio_normalizado = _normalizar_servicio(servicio or "")
    if not servicio_normalizado:
        return None
    return construir_mapa_servicios_genericos(taxonomia).get(servicio_normalizado)


def construir_mensaje_precision_cliente(
    servicio: Optional[str],
    taxonomia: Optional[Dict[str, Any]],
) -> Optional[str]:
    regla = _obtener_regla_para_servicio(servicio, taxonomia)
    if not regla:
        return None

    base = str(regla.get("client_prompt_template") or "").strip()
    dimensiones = [
        str(item).strip()
        for item in (regla.get("required_dimensions") or [])
        if str(item).strip()
    ]
    ejemplos = [str(item).strip() for item in (regla.get("sufficient_examples") or []) if str(item).strip()]

    if not base:
        return None

    partes = [base]
    if dimensiones:
        partes.append(f"Indícame: *{', '.join(dimensiones)}*.")
    if ejemplos:
        partes.append(f"Ejemplos: *{', '.join(ejemplos[:3])}*.")
    return " ".join(partes)


def _normalizar_servicio(texto: str) -> str:
    base = unicodedata.normalize("NFD", (texto or "").strip().lower())
    sin_acentos = "".join(ch for ch in base if unicodedata.category(ch) != "Mn")
    limpio = re.sub(r"[^a-z0-9\s]", " ", sin_acentos)
    return re.sub(r"\s+", " ", limpio).strip()


def _alias_activo(fila: Dict[str, Any]) -> bool:
    if "is_active" in fila:
        return bool(fila.get("is_active"))
    return str(fila.get("status") or "").strip().lower() in _STATUSES_PUBLICADOS


def _obtener_regla_para_servicio(
    servicio: Optional[str],
    taxonomia: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    match_canonico = detectar_servicio_canonico_en_taxonomia(servicio, taxonomia)
    dominio = (
        match_canonico.get("domain_code")
        if isinstance(match_canonico, dict)
        else detectar_dominio_generico_en_taxonomia(servicio, taxonomia)
    )
    if not dominio or not isinstance(taxonomia, dict):
        return None

    for item in taxonomia.get("domains") or []:
        if str(item.get("code") or "").strip().lower() != dominio:
            continue
        regla = item.get("precision_rule")
        if isinstance(regla, dict):
            return regla
    return None
