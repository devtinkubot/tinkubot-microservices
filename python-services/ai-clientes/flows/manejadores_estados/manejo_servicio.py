"""Módulo para el procesamiento del estado de espera de servicio."""

import logging
import re
import unicodedata
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_PALABRAS_VAGAS_OCUPACION = {
    "necesito",
    "busco",
    "quiero",
    "requiero",
    "ocupo",
    "solicito",
    "un",
    "una",
    "unos",
    "unas",
    "el",
    "la",
    "los",
    "las",
    "de",
    "del",
    "para",
    "por",
    "favor",
    "ayuda",
    "con",
    "urgente",
    "urgentemente",
}

_VERBOS_ACCION_USUARIO = {
    "llevar",
    "enviar",
    "mudar",
    "arreglar",
    "reparar",
    "destapar",
    "instalar",
    "configurar",
    "pintar",
    "construir",
    "hacer",
    "tramitar",
}

_RESPUESTAS_META_NO_UTILES = {
    "no entiendo",
    "no comprendo",
    "que",
    "qué",
    "como",
    "cómo",
    "eh",
    "mmm",
    "?",
    "no se",
    "no sé",
}


def _normalizar_texto(texto: str) -> str:
    base = unicodedata.normalize("NFD", (texto or "").strip().lower())
    sin_acentos = "".join(ch for ch in base if unicodedata.category(ch) != "Mn")
    limpio = re.sub(r"[^a-z0-9\s]", " ", sin_acentos)
    return re.sub(r"\s+", " ", limpio).strip()


def _tokens_relevantes(texto: str) -> list[str]:
    return [
        token
        for token in _normalizar_texto(texto).split()
        if token and token not in _PALABRAS_VAGAS_OCUPACION
    ]


def _es_solicitud_generica_ocupacion(
    texto: str,
    servicio_extraido: Optional[str],
) -> bool:
    if not servicio_extraido:
        return False
    tokens = _tokens_relevantes(texto)
    if any(token in _VERBOS_ACCION_USUARIO for token in tokens):
        return False
    # Solo bloqueamos ocupaciones de una sola palabra.
    # Frases de 2+ palabras como "asesor contable" ya deben avanzar
    # porque el prompt/IA puede convertirlas en una necesidad accionable.
    return len(tokens) == 1


def _es_respuesta_seguimiento_concreta(
    texto: str,
    servicio_extraido: Optional[str],
    servicio_hint: Optional[str],
) -> bool:
    """Relaja el gate cuando el usuario ya respondió a una repregunta.

    Si ya existe un hint y el usuario envía una frase corta pero concreta
    como "cambio de aceite" o "planos para una casa", debe poder pasar
    a confirmación sin volver a pedir "para qué".
    """
    if not servicio_hint or not servicio_extraido:
        return False
    if _es_respuesta_meta_no_util(texto):
        return False
    tokens_texto = _tokens_relevantes(texto)
    tokens_servicio = _tokens_relevantes(servicio_extraido)

    if any(token in _VERBOS_ACCION_USUARIO for token in tokens_texto):
        return True
    if len(tokens_texto) >= 2:
        return True
    return len(tokens_servicio) >= 3


def _construir_contexto_con_hint(
    texto: str,
    servicio_hint: Optional[str],
) -> str:
    hint = (servicio_hint or "").strip()
    detalle = (texto or "").strip()
    if hint and detalle:
        return f"Servicio de referencia: {hint}. Necesidad del usuario: {detalle}"
    return detalle or hint


def _es_respuesta_meta_no_util(texto: str) -> bool:
    normalizado = _normalizar_texto(texto)
    if not normalizado:
        return True
    if normalizado in _RESPUESTAS_META_NO_UTILES:
        return True
    return len(normalizado.split()) <= 2 and normalizado in {
        "no entiendo",
        "no se",
        "que hago",
    }


def _hint_usuario_legible(
    texto_usuario: str,
    servicio_extraido: Optional[str],
) -> str:
    """Devuelve un hint corto y entendible para repreguntar al usuario."""
    hint = (servicio_extraido or "").strip()
    if not hint:
        return (texto_usuario or "").strip()

    hint_norm = _normalizar_texto(hint)
    if hint_norm.startswith(("servicio de ", "servicio del ", "servicio de la ")):
        return (texto_usuario or "").strip()
    if len(hint.split()) > 5:
        return (texto_usuario or "").strip()
    return hint


def _normalizar_codigo_taxonomia(texto: Optional[str]) -> Optional[str]:
    valor = _normalizar_texto(texto or "")
    if not valor:
        return None
    return re.sub(r"\s+", "_", valor).strip("_") or None


def _extraer_perfil_servicio(
    valor: Any,
) -> Dict[str, Any]:
    if isinstance(valor, dict):
        search_profile = valor.get("search_profile")
        search_profile_dict = (
            search_profile if isinstance(search_profile, dict) else None
        )
        normalized_service = str(
            valor.get("normalized_service")
            or valor.get("service")
            or valor.get("service_name")
            or (search_profile_dict or {}).get("primary_service")
            or (search_profile_dict or {}).get("normalized_service")
            or ""
        ).strip()
        service_summary = str(
            valor.get("service_summary")
            or valor.get("service_full")
            or (search_profile_dict or {}).get("service_summary")
            or ""
        ).strip() or None
        domain = str(
            valor.get("domain")
            or (search_profile_dict or {}).get("domain")
            or ""
        ).strip() or None
        category = str(
            valor.get("category")
            or (search_profile_dict or {}).get("category")
            or ""
        ).strip() or None
        domain_code = str(
            valor.get("domain_code")
            or (search_profile_dict or {}).get("domain_code")
            or ""
        ).strip() or None
        category_name = str(
            valor.get("category_name")
            or (search_profile_dict or {}).get("category_name")
            or ""
        ).strip() or None

        if domain and not domain_code:
            domain_code = _normalizar_codigo_taxonomia(domain)
        if category and not category_name:
            category_name = _normalizar_texto(category) or category

        return {
            "normalized_service": normalized_service or None,
            "service_summary": service_summary,
            "domain": domain,
            "category": category,
            "domain_code": domain_code,
            "category_name": category_name,
            "search_profile": search_profile_dict,
        }

    servicio = str(valor or "").strip()
    return {
        "normalized_service": servicio or None,
        "service_summary": servicio or None,
        "domain": None,
        "category": None,
        "domain_code": None,
        "category_name": None,
        "search_profile": None,
    }


def _construir_search_profile_minimo(
    *,
    raw_input: str,
    primary_service: Optional[str],
    service_summary: Optional[str] = None,
    domain: Optional[str] = None,
    category: Optional[str] = None,
    confidence: float = 0.0,
    search_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    perfil = dict(search_profile or {})
    servicio = str(
        perfil.get("primary_service") or primary_service or ""
    ).strip()
    resumen = str(
        perfil.get("service_summary") or service_summary or ""
    ).strip() or None
    dominio = str(perfil.get("domain") or domain or "").strip() or None
    categoria = str(perfil.get("category") or category or "").strip() or None

    perfil["raw_input"] = (raw_input or "").strip()
    perfil["primary_service"] = servicio or None
    if resumen:
        perfil["service_summary"] = resumen
    perfil["domain"] = dominio
    perfil["category"] = categoria
    if dominio and not perfil.get("domain_code"):
        perfil["domain_code"] = _normalizar_codigo_taxonomia(dominio)
    if categoria and not perfil.get("category_name"):
        perfil["category_name"] = _normalizar_texto(categoria) or categoria
    if not perfil.get("signals"):
        signals: list[str] = []
        if resumen:
            signals.append(f"resumen del servicio: {resumen}")
        if servicio:
            signals.append(f"servicio objetivo: {servicio}")
        if dominio:
            signals.append(f"dominio: {dominio}")
        if categoria:
            signals.append(f"categoría: {categoria}")
        perfil["signals"] = signals
    perfil["confidence"] = max(0.0, min(1.0, float(confidence or 0.0)))
    perfil["source"] = perfil.get("source") or "client"
    return perfil


async def procesar_estado_esperando_servicio(
    flujo: Dict[str, Any],
    texto: Optional[str],
    saludos: set[str],
    prompt_inicial: str,
    extraer_fn: Callable[[str], Awaitable[Optional[Any]]],
    validar_necesidad_fn: Optional[Callable[[str], Awaitable[bool]]] = None,
    detectar_dominio_generico_fn: Optional[
        Callable[[Optional[str]], Awaitable[Optional[str]]]
    ] = None,
    construir_mensaje_precision_fn: Optional[
        Callable[[Optional[str]], Awaitable[Optional[str]]]
    ] = None,
    registrar_sugerencia_fn: Optional[
        Callable[[str, Optional[str]], Awaitable[None]]
    ] = None,
    registrar_evento_fn: Optional[
        Callable[..., Awaitable[None]]
    ] = None,
    generar_especializaciones_fn: Optional[
        Callable[[str], Awaitable[list[str]]]
    ] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Procesa el estado `awaiting_service`.

    Retorna una tupla con el flujo actualizado y el payload de respuesta.
    """

    limpio = (texto or "").strip()
    if not limpio or limpio.lower() in saludos:
        return flujo, {"response": prompt_inicial}

    # Evitar que números u opciones sueltas (ej: "1", "2", "a") se toman como servicio
    # NOTA: Permitimos "4" y "5" porque ahora se usan números 1-5 para proveedores
    if re.fullmatch(r"[6-9]\d*", limpio) or limpio.lower() in {
        "a",
        "b",
        "c",
        "d",
        "e",
    }:
        return flujo, {
            "response": (
                "Para continuar necesito el nombre del servicio que buscas "
                "(ej: plomero, electricista, manicure)."
            )
        }

    servicio_hint_existente = (flujo.get("service_candidate_hint") or "").strip()
    servicio_hint_label = (
        (flujo.get("service_candidate_hint_label") or "").strip()
        or servicio_hint_existente
    )

    if servicio_hint_existente and _es_respuesta_meta_no_util(limpio):
        from templates.mensajes.validacion import mensaje_aclarar_detalle_servicio

        flujo["state"] = "awaiting_service"
        return flujo, {
            "response": mensaje_aclarar_detalle_servicio(servicio_hint_label),
        }

    texto_para_extraccion = _construir_contexto_con_hint(limpio, servicio_hint_existente)

    es_necesidad = True
    if validar_necesidad_fn:
        try:
            es_necesidad = await validar_necesidad_fn(limpio)
        except Exception as exc:
            logger.warning(
                "⚠️ Error en validar_necesidad_fn (fallback a permitir): %s",
                exc,
            )
            es_necesidad = True

    try:
        logger.info(
            "🤖 Usando extracción IA para servicio: '%s...'",
            texto_para_extraccion[:50],
        )
        profesion = await extraer_fn(texto_para_extraccion)
    except Exception as exc:
        logger.warning(f"⚠️ Error en extraer_fn: {exc}")
        profesion = None

    perfil_servicio = _extraer_perfil_servicio(profesion)
    valor_servicio = (perfil_servicio.get("normalized_service") or "").strip()
    dominio_servicio = (perfil_servicio.get("domain") or "").strip()
    categoria_servicio = (perfil_servicio.get("category") or "").strip()
    dominio_code_servicio = (perfil_servicio.get("domain_code") or "").strip()
    categoria_name_servicio = (perfil_servicio.get("category_name") or "").strip()
    dominio_generico = None
    dominio_generico_origen = None
    if detectar_dominio_generico_fn:
        dominio_generico = await detectar_dominio_generico_fn(valor_servicio)
        if dominio_generico:
            dominio_generico_origen = "taxonomy"
    respuesta_seguimiento_concreta = _es_respuesta_seguimiento_concreta(
        limpio,
        valor_servicio,
        servicio_hint_existente,
    )
    solicitud_generica_ocupacion = bool(
        not servicio_hint_existente
        and _es_solicitud_generica_ocupacion(limpio, valor_servicio)
    )

    extraccion_completa = bool(valor_servicio and dominio_servicio and categoria_servicio)
    if ((not es_necesidad and not respuesta_seguimiento_concreta) or solicitud_generica_ocupacion) and not extraccion_completa:
        hint = valor_servicio or limpio
        hint_usuario = _hint_usuario_legible(limpio, valor_servicio)
        search_profile = _construir_search_profile_minimo(
            raw_input=texto or limpio,
            primary_service=valor_servicio or hint,
            service_summary=perfil_servicio.get("service_summary") or valor_servicio or hint,
            domain=dominio_servicio or None,
            category=categoria_servicio or None,
            confidence=0.0,
            search_profile=perfil_servicio.get("search_profile"),
        )
        flujo["state"] = "awaiting_service"
        flujo["service_candidate_hint"] = hint
        flujo["service_candidate_hint_label"] = hint_usuario
        flujo.pop("service_domain", None)
        flujo.pop("service_domain_code", None)
        flujo.pop("service_category", None)
        flujo.pop("service_category_name", None)
        if dominio_servicio:
            flujo["service_domain"] = dominio_servicio
        if categoria_servicio:
            flujo["service_category"] = categoria_servicio
        if dominio_code_servicio:
            flujo["service_domain_code"] = dominio_code_servicio
        if categoria_name_servicio:
            flujo["service_category_name"] = categoria_name_servicio
        flujo.pop("service_candidate", None)
        flujo.pop("service", None)
        flujo.pop("service_full", None)
        flujo.pop("descripcion_problema", None)
        flujo["search_profile"] = search_profile
        from templates.mensajes.validacion import (
            construir_lista_especializaciones,
            mensaje_solicitar_detalle_servicio,
        )

        logger.info(
            "occupation_only_blocked normalized_input='%s' extracted='%s'",
            limpio.lower()[:120],
            hint,
        )

        especializaciones: list[str] = []
        if generar_especializaciones_fn:
            try:
                especializaciones = await generar_especializaciones_fn(
                    hint_usuario or hint
                )
            except Exception as exc:
                logger.warning("⚠️ Error obteniendo especializaciones: %s", exc)

        if especializaciones:
            flujo["specialization_options"] = especializaciones
            return flujo, {
                "response": mensaje_solicitar_detalle_servicio(hint_usuario),
                "ui": construir_lista_especializaciones(
                    hint_usuario or hint, especializaciones
                ),
            }

        return flujo, {
            "response": mensaje_solicitar_detalle_servicio(hint_usuario),
        }

    if not valor_servicio:
        return flujo, {
            "response": (
                "No pude identificar con claridad el servicio. "
                "Descríbelo de forma más concreta (ej: desarrollador web, "
                "plomero, electricista, diseñador gráfico)."
            )
        }

    if dominio_generico:
        if registrar_sugerencia_fn:
            await registrar_sugerencia_fn(valor_servicio, limpio)
        if registrar_evento_fn:
            await registrar_evento_fn(
                event_name="generic_service_blocked",
                domain_code=dominio_generico,
                fallback_source=dominio_generico_origen,
                service_text=valor_servicio,
                context_excerpt=limpio,
        )
        flujo["state"] = "awaiting_service"
        flujo["service_candidate_hint"] = valor_servicio
        flujo["service_candidate_hint_label"] = valor_servicio
        flujo.pop("service_domain", None)
        flujo.pop("service_domain_code", None)
        flujo.pop("service_category", None)
        flujo.pop("service_category_name", None)
        if dominio_servicio:
            flujo["service_domain"] = dominio_servicio
        if categoria_servicio:
            flujo["service_category"] = categoria_servicio
        if dominio_code_servicio:
            flujo["service_domain_code"] = dominio_code_servicio
        if categoria_name_servicio:
            flujo["service_category_name"] = categoria_name_servicio
        flujo.pop("service_candidate", None)
        flujo.pop("service", None)
        flujo.pop("service_full", None)
        flujo.pop("descripcion_problema", None)
        flujo["search_profile"] = _construir_search_profile_minimo(
            raw_input=texto or limpio,
            primary_service=valor_servicio,
            domain=dominio_servicio or None,
            category=categoria_servicio or None,
            confidence=0.0,
            search_profile=perfil_servicio.get("search_profile"),
        )
        from templates.mensajes.validacion import mensaje_solicitar_precision_servicio

        mensaje_precision = (
            await construir_mensaje_precision_fn(valor_servicio)
            if construir_mensaje_precision_fn
            else None
        )
        if not mensaje_precision:
            logger.warning(
                "precision_prompt_fallback_used domain='%s' service='%s' origin='%s'",
                dominio_generico,
                valor_servicio,
                dominio_generico_origen or "unknown",
            )
            if registrar_evento_fn:
                await registrar_evento_fn(
                    event_name="precision_prompt_fallback_used",
                    domain_code=dominio_generico,
                    fallback_source=dominio_generico_origen,
                    service_text=valor_servicio,
                    context_excerpt=limpio,
                )
        if registrar_evento_fn:
            await registrar_evento_fn(
                event_name="clarification_requested",
                domain_code=dominio_generico,
                fallback_source=dominio_generico_origen,
                service_text=valor_servicio,
                context_excerpt=limpio,
            )
        logger.info(
            "critical_generic_service_blocked domain='%s' service='%s' input='%s' origin='%s'",
            dominio_generico,
            valor_servicio,
            limpio[:120],
            dominio_generico_origen or "unknown",
        )
        return flujo, {
            "response": mensaje_precision
            or mensaje_solicitar_precision_servicio(valor_servicio),
        }

    if not dominio_servicio or not categoria_servicio:
        search_profile = _construir_search_profile_minimo(
            raw_input=texto or limpio,
            primary_service=valor_servicio,
            service_summary=perfil_servicio.get("service_summary") or valor_servicio,
            domain=dominio_servicio or None,
            category=categoria_servicio or None,
            confidence=0.0,
            search_profile=perfil_servicio.get("search_profile"),
        )
        flujo["state"] = "awaiting_service"
        flujo["service_candidate_hint"] = valor_servicio
        flujo["service_candidate_hint_label"] = valor_servicio
        flujo.pop("service_domain", None)
        flujo.pop("service_domain_code", None)
        flujo.pop("service_category", None)
        flujo.pop("service_category_name", None)
        if dominio_servicio:
            flujo["service_domain"] = dominio_servicio
        if categoria_servicio:
            flujo["service_category"] = categoria_servicio
        if dominio_code_servicio:
            flujo["service_domain_code"] = dominio_code_servicio
        if categoria_name_servicio:
            flujo["service_category_name"] = categoria_name_servicio
        flujo.pop("service_candidate", None)
        flujo.pop("service", None)
        flujo.pop("service_full", None)
        flujo.pop("descripcion_problema", None)
        flujo["search_profile"] = search_profile
        from templates.mensajes.validacion import mensaje_solicitar_precision_servicio

        logger.info(
            "taxonomy_incomplete_blocked normalized_input='%s' extracted='%s' domain='%s' category='%s'",
            limpio.lower()[:120],
            valor_servicio,
            dominio_servicio or "",
            categoria_servicio or "",
        )
        return flujo, {
            "response": mensaje_solicitar_precision_servicio(valor_servicio),
        }

    if respuesta_seguimiento_concreta:
        logger.info(
            "followup_specific_need_accepted normalized_input='%s' extracted='%s'",
            limpio.lower()[:120],
            valor_servicio,
        )

    partes_contexto = []
    if servicio_hint_existente:
        partes_contexto.append(f"Servicio de referencia: {servicio_hint_existente}")
    if valor_servicio:
        partes_contexto.append(f"Servicio normalizado: {valor_servicio}")
    if dominio_servicio:
        partes_contexto.append(f"Dominio: {dominio_servicio}")
    if categoria_servicio:
        partes_contexto.append(f"Categoría: {categoria_servicio}")
    detalle_contexto = (texto or limpio).strip()
    if detalle_contexto:
        partes_contexto.append(f"Necesidad del usuario: {detalle_contexto}")
    contexto_busqueda = ". ".join(partes_contexto) if partes_contexto else detalle_contexto
    search_profile = _construir_search_profile_minimo(
        raw_input=texto or limpio,
        primary_service=valor_servicio,
        service_summary=perfil_servicio.get("service_summary") or valor_servicio,
        domain=dominio_servicio or None,
        category=categoria_servicio or None,
        confidence=0.92 if dominio_servicio or categoria_servicio else 0.8,
        search_profile=perfil_servicio.get("search_profile"),
    )
    flujo.update(
        {
            "service_candidate": valor_servicio,
            "service_summary": perfil_servicio.get("service_summary")
            or contexto_busqueda,
            "service_full": contexto_busqueda,
            "descripcion_problema": texto or limpio,
            "service_domain": dominio_servicio or None,
            "service_domain_code": dominio_code_servicio or None,
            "service_category": categoria_servicio or None,
            "service_category_name": categoria_name_servicio or None,
            "search_profile": search_profile,
            "state": "confirm_service",
        }
    )
    flujo.pop("service_candidate_hint", None)
    flujo.pop("service_candidate_hint_label", None)
    from templates.mensajes.validacion import (
        mensaje_confirmar_servicio,
        ui_confirmar_servicio,
    )

    service_summary_texto = (perfil_servicio.get("service_summary") or "").strip()
    return flujo, {
        "response": mensaje_confirmar_servicio(valor_servicio, service_summary_texto),
        "ui": ui_confirmar_servicio(),
    }
