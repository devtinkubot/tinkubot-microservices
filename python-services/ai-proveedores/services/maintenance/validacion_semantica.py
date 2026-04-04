"""Validación semántica de servicios de proveedores."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from config.configuracion import configuracion
from services.maintenance.clasificacion_semantica import (
    construir_service_summary,
    normalizar_domain_code_operativo,
    obtener_catalogo_dominios_liviano,
)
from services.shared import (
    PROMPT_CATALOGO_SIN_DOMINIO,
    construir_prompt_sistema_enriquecimiento_servicios,
    construir_prompt_usuario_enriquecimiento_servicios,
)
from utils import (
    limpiar_texto_servicio,
    normalizar_texto_para_busqueda,
    normalizar_texto_visible_corto,
)

logger = logging.getLogger(__name__)

_RECHAZOS_DIRECTOS = {
    "hola",
    "hola hola",
    "buenas",
    "buen dia",
    "buenos dias",
    "buenas tardes",
    "buenas noches",
    "gracias",
    "ok",
    "okay",
    "info",
    "informacion",
    "información",
    "ayuda",
    "test",
    "prueba",
}

_GENERICOS_DIRECTOS = {
    "servicio",
    "servicios",
    "servicios varios",
    "servicios generales",
    "servicio general",
    "de todo",
    "hago de todo",
    "trabajo de todo",
    "varios",
    "general",
    "multi servicios",
    "multiservicios",
}

_ACLARACIONES_POR_CLAVE = {
    "asesoria legal": "Indica el trámite o área legal exacta con la que trabajas.",
    "asesoria juridica": "Indica el trámite o área legal exacta con la que trabajas.",
    "transporte": (
        "Indica el tipo de transporte, alcance y carga con la que trabajas."
    ),
    "consultoria": ("Indica el tipo de consultoría o área exacta en la que trabajas."),
    "consultoria empresarial": (
        "Indica el tipo de consultoría o área exacta en la que trabajas."
    ),
    "marketing": "Indica el servicio de marketing exacto que realizas.",
    "servicios informaticos": ("Indica el servicio tecnológico exacto que realizas."),
    "desarrollo de software": (
        "Indica el tipo de software o solución exacta que desarrollas."
    ),
}


def _resultado(
    *,
    is_valid_service: bool,
    needs_clarification: bool,
    normalized_service: str,
    reason: str,
    domain_resolution_status: str,
    clarification_question: Optional[str] = None,
    domain_code: Optional[str] = None,
    resolved_domain_code: Optional[str] = None,
    category_name: Optional[str] = None,
    service_summary: Optional[str] = None,
    confidence: float = 0.0,
) -> Dict[str, Any]:
    normalized_domain = normalizar_domain_code_operativo(domain_code)
    resolved_domain = normalizar_domain_code_operativo(resolved_domain_code)
    normalized_service_visible = " ".join(str(normalized_service or "").strip().split())
    proposed_category = category_name
    proposed_summary = str(service_summary or "").strip() or construir_service_summary(
        service_name=normalized_service_visible or normalized_service,
        category_name=category_name,
        domain_code=domain_code,
    )
    return {
        "is_valid_service": is_valid_service,
        "needs_clarification": needs_clarification,
        "normalized_service": normalized_service_visible,
        "domain_resolution_status": domain_resolution_status,
        "domain_code": normalized_domain,
        "resolved_domain_code": resolved_domain,
        "category_name": category_name,
        "service_summary": proposed_summary,
        "proposed_category_name": proposed_category,
        "proposed_service_summary": proposed_summary,
        "confidence": max(0.0, min(1.0, float(confidence))),
        "reason": reason,
        "clarification_question": clarification_question,
    }


def _pregunta_aclaracion(normalizado: str) -> Optional[str]:
    for clave, pregunta in _ACLARACIONES_POR_CLAVE.items():
        if clave in normalizado:
            return pregunta
    if "legal" in normalizado or "abogado" in normalizado:
        return "Indica el trámite o área legal exacta con la que trabajas."
    if (
        "transporte" in normalizado
        or "conductor" in normalizado
        or "chofer" in normalizado
    ):
        return "Indica el tipo de transporte, alcance y carga con la que trabajas."
    if "software" in normalizado:
        return "Indica el tipo de software o solución exacta que desarrollas."
    return "Indica el servicio o especialidad exacta que ofreces."


def _codigos_catalogo(catalogo_dominios: Optional[list[Dict[str, str]]]) -> set[str]:
    return {
        code
        for code in (
            normalizar_domain_code_operativo(item.get("code"))
            for item in (catalogo_dominios or [])
        )
        if code
    }


def _validacion_heuristica(
    *,
    raw_service_text: str,
    service_name: str,
) -> Dict[str, Any]:
    raw_normalizado = normalizar_texto_para_busqueda(raw_service_text)
    service_normalizado = normalizar_texto_para_busqueda(service_name)
    clave = limpiar_texto_servicio(service_name)

    if not service_normalizado:
        return _resultado(
            is_valid_service=False,
            needs_clarification=False,
            normalized_service=service_name,
            reason="empty_service",
            domain_resolution_status="rejected",
        )

    if (
        raw_normalizado in _RECHAZOS_DIRECTOS
        or service_normalizado in _RECHAZOS_DIRECTOS
    ):
        return _resultado(
            is_valid_service=False,
            needs_clarification=False,
            normalized_service=service_name,
            reason="non_service_text",
            domain_resolution_status="rejected",
        )

    if (
        raw_normalizado in _GENERICOS_DIRECTOS
        or service_normalizado in _GENERICOS_DIRECTOS
    ):
        return _resultado(
            is_valid_service=False,
            needs_clarification=True,
            normalized_service=service_name,
            reason="generic_service",
            domain_resolution_status="clarification_required",
            clarification_question=_pregunta_aclaracion(service_normalizado),
            confidence=0.25,
        )

    if service_normalizado == "servicio normalizado":
        return _resultado(
            is_valid_service=False,
            needs_clarification=True,
            normalized_service=service_name,
            reason="placeholder_service",
            domain_resolution_status="clarification_required",
            clarification_question=(
                "Escribe el servicio o especialidad exacta que realmente ofreces."
            ),
            confidence=0.2,
        )

    if clave in _ACLARACIONES_POR_CLAVE:
        return _resultado(
            is_valid_service=False,
            needs_clarification=True,
            normalized_service=service_name,
            reason="generic_service",
            domain_resolution_status="clarification_required",
            clarification_question=_pregunta_aclaracion(clave),
            confidence=0.35,
        )

    return _resultado(
        is_valid_service=True,
        needs_clarification=False,
        normalized_service=service_name,
        reason="heuristic_accept",
        domain_resolution_status="clarification_required",
        confidence=0.55,
    )


def _clasificacion_completa(
    data: Dict[str, Any],
    *,
    codigos_catalogo: set[str],
) -> bool:
    domain_code = normalizar_domain_code_operativo(
        data.get("resolved_domain_code") or data.get("domain_code")
    )
    category_name = str(data.get("category_name") or "").strip()
    status = str(data.get("status") or "").strip().lower()
    return bool(
        status == "accepted"
        and domain_code
        and category_name
        and (not codigos_catalogo or domain_code in codigos_catalogo)
    )


async def _clasificar_servicio_con_ia(
    *,
    cliente_openai: Any,
    raw_service_text: str,
    service_name: str,
    dominios_prompt: str,
    modo_estricto: bool,
    timeout: float,
) -> Optional[Dict[str, Any]]:
    try:
        respuesta = await cliente_openai.chat.completions.create(
            model=configuracion.openai_chat_model,
            messages=[
                {
                    "role": "system",
                    "content": construir_prompt_sistema_enriquecimiento_servicios(),
                },
                {
                    "role": "user",
                    "content": construir_prompt_usuario_enriquecimiento_servicios(
                        raw_service_text,
                        dominios_prompt,
                        modo_estricto=modo_estricto,
                    ),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "service_enrichment",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "normalized_service": {"type": "string"},
                            "domain_code": {"type": ["string", "null"]},
                            "category_name": {"type": ["string", "null"]},
                            "service_summary": {"type": "string"},
                            "confidence": {"type": "number"},
                            "reason": {"type": "string"},
                            "clarification_question": {"type": ["string", "null"]},
                            "status": {
                                "type": "string",
                                "enum": ["accepted", "clarification_required", "rejected"],
                            },
                        },
                        "required": [
                            "normalized_service",
                            "domain_code",
                            "category_name",
                            "service_summary",
                            "confidence",
                            "reason",
                            "clarification_question",
                            "status",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            temperature=configuracion.openai_temperature_precisa,
            timeout=timeout,
        )
        contenido = (respuesta.choices[0].message.content or "").strip()
        data = json.loads(contenido)
    except Exception as exc:
        logger.warning(
            "⚠️ No se pudo validar servicio con IA (modo_estricto=%s): %s",
            modo_estricto,
            exc,
        )
        return None

    normalized_service = normalizar_texto_visible_corto(
        str(data.get("normalized_service") or service_name).strip() or service_name
    )
    domain_code = normalizar_domain_code_operativo(
        str(data.get("domain_code") or "").strip() or None
    )
    category_name = str(data.get("category_name") or "").strip() or None
    service_summary = str(data.get("service_summary") or "").strip() or None
    reason = str(data.get("reason") or "ai_validation").strip() or "ai_validation"
    clarification_question = (
        str(data.get("clarification_question") or "").strip() or None
    )
    confidence = float(data.get("confidence") or 0.0)
    status = str(data.get("status") or "").strip().lower() or "clarification_required"
    return {
        "normalized_service": normalized_service,
        "domain_code": domain_code,
        "resolved_domain_code": domain_code,
        "category_name": category_name,
        "service_summary": service_summary,
        "confidence": confidence,
        "reason": reason,
        "clarification_question": clarification_question,
        "status": status,
    }


async def enriquecer_servicio_semanticamente(
    *,
    cliente_openai: Optional[Any],
    supabase: Any,
    raw_service_text: str,
    service_name: str,
    timeout: float = 8.0,
) -> Dict[str, Any]:
    """Enriquece un servicio crudo con dominio, categoría y resumen."""
    heuristico = _validacion_heuristica(
        raw_service_text=raw_service_text,
        service_name=service_name,
    )
    if not heuristico["is_valid_service"] or heuristico["needs_clarification"]:
        logger.info(
            "service_validation_heuristic_result",
            extra={
                "raw_service_text": raw_service_text,
                "service_name": service_name,
                "reason": heuristico["reason"],
                "needs_clarification": heuristico["needs_clarification"],
            },
        )
        return heuristico

    if not cliente_openai or not hasattr(cliente_openai, "chat"):
        return heuristico

    catalogo_dominios = await obtener_catalogo_dominios_liviano(supabase)
    codigos_catalogo = _codigos_catalogo(catalogo_dominios)
    dominios_prompt = "\n".join(
        f"- {item['code']}: {item['display_name']}"
        + (f" ({item['description']})" if item.get("description") else "")
        for item in catalogo_dominios[:40]
    )
    if not dominios_prompt:
        dominios_prompt = PROMPT_CATALOGO_SIN_DOMINIO

    primera = await _clasificar_servicio_con_ia(
        cliente_openai=cliente_openai,
        raw_service_text=raw_service_text,
        service_name=service_name,
        dominios_prompt=dominios_prompt,
        modo_estricto=False,
        timeout=timeout,
    )
    if primera and _clasificacion_completa(primera, codigos_catalogo=codigos_catalogo):
        return _resultado(
            is_valid_service=True,
            needs_clarification=False,
            normalized_service=primera["normalized_service"],
            reason=primera["reason"],
            domain_resolution_status="matched",
            domain_code=primera["resolved_domain_code"],
            resolved_domain_code=primera["resolved_domain_code"],
            category_name=primera["category_name"],
            service_summary=primera["service_summary"],
            confidence=primera["confidence"] or heuristico["confidence"],
            clarification_question=None,
        )

    segunda = await _clasificar_servicio_con_ia(
        cliente_openai=cliente_openai,
        raw_service_text=raw_service_text,
        service_name=service_name,
        dominios_prompt=dominios_prompt,
        modo_estricto=True,
        timeout=timeout,
    )
    if segunda and _clasificacion_completa(segunda, codigos_catalogo=codigos_catalogo):
        return _resultado(
            is_valid_service=True,
            needs_clarification=False,
            normalized_service=segunda["normalized_service"],
            reason=segunda["reason"],
            domain_resolution_status="matched",
            domain_code=segunda["resolved_domain_code"],
            resolved_domain_code=segunda["resolved_domain_code"],
            category_name=segunda["category_name"],
            service_summary=segunda["service_summary"],
            confidence=segunda["confidence"] or heuristico["confidence"],
            clarification_question=None,
        )

    fallback = segunda or primera or {}
    status = str(fallback.get("status") or "").strip().lower()
    if status == "rejected":
        return _resultado(
            is_valid_service=False,
            needs_clarification=False,
            normalized_service=str(
                fallback.get("normalized_service") or service_name
            ).strip()
            or service_name,
            reason=str(fallback.get("reason") or "ai_rejected").strip() or "ai_rejected",
            domain_resolution_status="rejected",
            confidence=float(fallback.get("confidence") or heuristico["confidence"]),
        )

    return _resultado(
        is_valid_service=False,
        needs_clarification=True,
        normalized_service=str(
            fallback.get("normalized_service") or service_name
        ).strip()
        or service_name,
        reason="domain_or_category_not_resolved",
        domain_resolution_status="clarification_required",
        clarification_question=(
            fallback.get("clarification_question")
            or _pregunta_aclaracion(
                normalizar_texto_para_busqueda(
                    str(fallback.get("normalized_service") or service_name)
                )
            )
        ),
        domain_code=fallback.get("domain_code"),
        category_name=fallback.get("category_name"),
        service_summary=fallback.get("service_summary"),
        confidence=float(fallback.get("confidence") or heuristico["confidence"]),
    )


async def validar_servicio_semanticamente(
    *,
    cliente_openai: Optional[Any],
    supabase: Any,
    raw_service_text: str,
    service_name: str,
    timeout: float = 8.0,
) -> Dict[str, Any]:
    """Compatibilidad: devuelve el resultado enriquecido con forma legacy."""
    return await enriquecer_servicio_semanticamente(
        cliente_openai=cliente_openai,
        supabase=supabase,
        raw_service_text=raw_service_text,
        service_name=service_name,
        timeout=timeout,
    )
