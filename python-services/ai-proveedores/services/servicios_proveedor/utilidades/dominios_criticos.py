"""Reglas para detectar servicios genéricos de dominios críticos."""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

from services.taxonomia import LectorTaxonomiaPublicada
from services.taxonomia import registrar_evento_taxonomia_runtime
from services.taxonomia import registrar_sugerencia_taxonomia

_MAPA_SERVICIOS_GENERICOS_DINAMICO: dict[str, str] = {}
_REGLAS_DOMINIO_DINAMICAS: dict[str, dict] = {}
_LECTOR_TAXONOMIA = LectorTaxonomiaPublicada()


def normalizar_servicio_critico(texto: str) -> str:
    """Normaliza servicio para comparaciones exactas."""
    base = unicodedata.normalize("NFD", (texto or "").strip().lower())
    sin_acentos = "".join(ch for ch in base if unicodedata.category(ch) != "Mn")
    limpio = re.sub(r"[^a-z0-9\s]", " ", sin_acentos)
    return re.sub(r"\s+", " ", limpio).strip()


def detectar_dominio_critico_generico(servicio: str) -> Optional[str]:
    """Retorna dominio si el servicio es demasiado genérico."""
    return clasificar_servicio_critico(servicio).get("domain")


def es_servicio_critico_generico(servicio: str) -> bool:
    return clasificar_servicio_critico(servicio).get("specificity") == "insufficient"


def mensaje_pedir_precision_servicio(servicio: str) -> str:
    """Pide mayor precisión según dominio crítico."""
    clasificacion = clasificar_servicio_critico(servicio)
    dominio = clasificacion.get("domain")
    if clasificacion.get("clarification_question"):
        return str(clasificacion["clarification_question"])

    regla = _REGLAS_DOMINIO_DINAMICAS.get(dominio or "")
    if regla:
        base = str(regla.get("provider_prompt_template") or "").strip()
        dimensiones = [
            str(item).strip()
            for item in (regla.get("required_dimensions") or [])
            if str(item).strip()
        ]
        ejemplos = [
            str(item).strip()
            for item in (regla.get("sufficient_examples") or [])
            if str(item).strip()
        ]
        if base:
            partes = [base]
            if dimensiones:
                partes.append(f"Indica: *{', '.join(dimensiones)}*.")
            if ejemplos:
                partes.append(f"Ejemplos: *{', '.join(ejemplos[:3])}*.")
            return " ".join(partes)

    return (
        "*Ese servicio está muy general.* "
        "Por favor descríbelo con más precisión antes de guardarlo."
    )


def clasificar_servicio_critico(servicio: str) -> dict:
    dominio, source = _detectar_dominio_critico_generico_bruto(servicio)
    regla = _REGLAS_DOMINIO_DINAMICAS.get(dominio or "")
    missing_dimensions = [
        str(item).strip()
        for item in (regla.get("required_dimensions") or [])
        if str(item).strip()
    ] if regla else []
    clarification_question = None
    if regla:
        clarification_question = mensaje_pedir_precision_servicio_desde_regla(regla)

    return {
        "domain": dominio,
        "service_candidate": (servicio or "").strip() or None,
        "specificity": "insufficient" if dominio else "unknown",
        "missing_dimensions": missing_dimensions,
        "clarification_question": clarification_question,
        "confidence": 0.99 if dominio else 0.0,
        "canonical_match": None,
        "source": source,
    }


def _detectar_dominio_critico_generico_bruto(servicio: str) -> tuple[Optional[str], str]:
    servicio_normalizado = normalizar_servicio_critico(servicio)
    dominio_dinamico = _MAPA_SERVICIOS_GENERICOS_DINAMICO.get(servicio_normalizado)
    if dominio_dinamico:
        return dominio_dinamico, "taxonomy"
    return None, "none"


def mensaje_pedir_precision_servicio_desde_regla(regla: dict) -> Optional[str]:
    base = str(regla.get("provider_prompt_template") or "").strip()
    dimensiones = [
        str(item).strip()
        for item in (regla.get("required_dimensions") or [])
        if str(item).strip()
    ]
    ejemplos = [
        str(item).strip()
        for item in (regla.get("sufficient_examples") or [])
        if str(item).strip()
    ]
    if not base:
        return None
    partes = [base]
    if dimensiones:
        partes.append(f"Indica: *{', '.join(dimensiones)}*.")
    if ejemplos:
        partes.append(f"Ejemplos: *{', '.join(ejemplos[:3])}*.")
    return " ".join(partes)


def formatear_servicio_generico_pendiente(servicio: str) -> str:
    texto = (servicio or "").strip()
    if not texto:
        return ""
    return f"{texto} (genérico)"


async def refrescar_taxonomia_dominios_criticos(force_refresh: bool = False) -> None:
    taxonomia = await _LECTOR_TAXONOMIA.obtener_taxonomia_publicada(
        force_refresh=force_refresh
    )
    _MAPA_SERVICIOS_GENERICOS_DINAMICO.clear()
    _MAPA_SERVICIOS_GENERICOS_DINAMICO.update(
        _construir_mapa_desde_taxonomia(taxonomia)
    )
    _REGLAS_DOMINIO_DINAMICAS.clear()
    _REGLAS_DOMINIO_DINAMICAS.update(_extraer_reglas_por_dominio(taxonomia))


async def registrar_sugerencia_servicio_generico(
    servicio: str,
    *,
    contexto: Optional[str] = None,
) -> None:
    try:
        from infrastructure.redis import cliente_redis
        from principal import supabase

        await registrar_sugerencia_taxonomia(
            supabase=supabase,
            redis_client=cliente_redis,
            source_channel="provider",
            source_text=servicio,
            context_excerpt=contexto,
            proposed_domain_code=detectar_dominio_critico_generico(servicio),
        )
    except Exception:
        return


async def registrar_evento_servicio_generico(
    *,
    event_name: str,
    servicio: str,
    dominio: Optional[str],
    source: str,
    contexto: Optional[str] = None,
) -> None:
    try:
        from principal import supabase

        await registrar_evento_taxonomia_runtime(
            supabase=supabase,
            source_channel="provider",
            event_name=event_name,
            domain_code=dominio,
            fallback_source=source,
            service_text=servicio,
            context_excerpt=contexto,
        )
    except Exception:
        return


def _construir_mapa_desde_taxonomia(taxonomia: dict) -> dict[str, str]:
    mapa: dict[str, str] = {}
    for dominio in taxonomia.get("domains") or []:
        codigo = str(dominio.get("code") or "").strip().lower()
        if not codigo:
            continue

        for alias in dominio.get("aliases") or []:
            alias_normalizado = normalizar_servicio_critico(
                alias.get("alias_normalized") or alias.get("alias_text") or ""
            )
            if alias_normalizado:
                mapa[alias_normalizado] = codigo

        for regla in dominio.get("rules") or []:
            for ejemplo in regla.get("generic_examples") or []:
                ejemplo_normalizado = normalizar_servicio_critico(ejemplo or "")
                if ejemplo_normalizado:
                    mapa[ejemplo_normalizado] = codigo

    return mapa


def _extraer_reglas_por_dominio(taxonomia: dict) -> dict[str, dict]:
    reglas: dict[str, dict] = {}
    for dominio in taxonomia.get("domains") or []:
        codigo = str(dominio.get("code") or "").strip().lower()
        if not codigo:
            continue
        reglas_dominio = dominio.get("rules") or []
        if reglas_dominio and isinstance(reglas_dominio[0], dict):
            reglas[codigo] = reglas_dominio[0]
    return reglas
