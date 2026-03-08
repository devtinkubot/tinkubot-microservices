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

_SERVICIOS_GENERICOS_CRITICOS = {
    "asesoria legal": "legal",
    "servicio legal": "legal",
    "legal": "legal",
    "transporte mercancias": "transporte",
    "transporte mercaderia": "transporte",
    "transporte de mercancias": "transporte",
    "transporte de mercaderia": "transporte",
    "transporte carga": "transporte",
    "transporte de carga": "transporte",
    "transporte terrestre": "transporte",
    "transporte maritimo": "transporte",
    "transporte aereo": "transporte",
    "servicios tecnologicos": "tecnologia",
    "servicio tecnologico": "tecnologia",
    "consultoria tecnologica": "tecnologia",
    "consultoria tecnologia": "tecnologia",
    "desarrollo tecnologico": "tecnologia",
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
    return 0 < len(tokens) <= 2


def _construir_contexto_con_hint(
    texto: str,
    servicio_hint: Optional[str],
) -> str:
    hint = (servicio_hint or "").strip()
    detalle = (texto or "").strip()
    if hint and detalle:
        return f"Servicio de referencia: {hint}. Necesidad del usuario: {detalle}"
    return detalle or hint


def _detectar_servicio_generico_critico(servicio: Optional[str]) -> Optional[str]:
    return _SERVICIOS_GENERICOS_CRITICOS.get(_normalizar_texto(servicio or ""))


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


async def procesar_estado_esperando_servicio(
    flujo: Dict[str, Any],
    texto: Optional[str],
    saludos: set[str],
    prompt_inicial: str,
    extraer_fn: Callable[[str], Awaitable[Optional[str]]],
    validar_necesidad_fn: Optional[Callable[[str], Awaitable[bool]]] = None,
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

    valor_servicio = (profesion or "").strip()
    if not es_necesidad or _es_solicitud_generica_ocupacion(limpio, valor_servicio):
        hint = valor_servicio or limpio
        hint_usuario = _hint_usuario_legible(limpio, valor_servicio)
        flujo["state"] = "awaiting_service"
        flujo["service_candidate_hint"] = hint
        flujo["service_candidate_hint_label"] = hint_usuario
        flujo.pop("service_candidate", None)
        flujo.pop("service", None)
        flujo.pop("descripcion_problema", None)
        from templates.mensajes.validacion import mensaje_solicitar_detalle_servicio

        logger.info(
            "occupation_only_blocked normalized_input='%s' extracted='%s'",
            limpio.lower()[:120],
            hint,
        )
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

    dominio_generico = _detectar_servicio_generico_critico(valor_servicio)
    if dominio_generico:
        flujo["state"] = "awaiting_service"
        flujo["service_candidate_hint"] = valor_servicio
        flujo["service_candidate_hint_label"] = valor_servicio
        flujo.pop("service_candidate", None)
        flujo.pop("service", None)
        flujo.pop("descripcion_problema", None)
        from templates.mensajes.validacion import mensaje_solicitar_precision_servicio

        logger.info(
            "critical_generic_service_blocked domain='%s' service='%s' input='%s'",
            dominio_generico,
            valor_servicio,
            limpio[:120],
        )
        return flujo, {
            "response": mensaje_solicitar_precision_servicio(valor_servicio),
        }

    contexto_busqueda = _construir_contexto_con_hint(texto or limpio, servicio_hint_existente)
    flujo.update(
        {
            "service_candidate": valor_servicio,
            "service_full": contexto_busqueda,
            "descripcion_problema": contexto_busqueda,
            "state": "confirm_service",
        }
    )
    flujo.pop("service_candidate_hint", None)
    flujo.pop("service_candidate_hint_label", None)
    from templates.mensajes.validacion import (
        mensaje_confirmar_servicio,
        ui_confirmar_servicio,
    )

    return flujo, {
        "response": mensaje_confirmar_servicio(valor_servicio),
        "ui": ui_confirmar_servicio(),
    }
