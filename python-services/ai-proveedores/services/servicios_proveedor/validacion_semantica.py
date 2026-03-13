"""Validación semántica de servicios de proveedores."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from services.servicios_proveedor.clasificacion_semantica import (
    construir_service_summary,
    normalizar_domain_code_operativo,
    obtener_catalogo_dominios_liviano,
)
from services.servicios_proveedor.utilidades import limpiar_texto_servicio
from services.servicios_proveedor.utilidades import normalizar_texto_para_busqueda

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
    "transporte": "Indica el tipo de transporte, alcance y carga con la que trabajas.",
    "consultoria": "Indica el tipo de consultoría o área exacta en la que trabajas.",
    "consultoria empresarial": "Indica el tipo de consultoría o área exacta en la que trabajas.",
    "marketing": "Indica el servicio de marketing exacto que realizas.",
    "servicios informaticos": "Indica el servicio tecnológico exacto que realizas.",
    "desarrollo de software": "Indica el tipo de software o solución exacta que desarrollas.",
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
    proposed_category = category_name
    proposed_summary = str(service_summary or "").strip() or construir_service_summary(
        service_name=normalized_service,
        category_name=category_name,
        domain_code=domain_code,
    )
    return {
        "is_valid_service": is_valid_service,
        "needs_clarification": needs_clarification,
        "normalized_service": normalized_service,
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
    if "transporte" in normalizado or "conductor" in normalizado or "chofer" in normalizado:
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

    if raw_normalizado in _RECHAZOS_DIRECTOS or service_normalizado in _RECHAZOS_DIRECTOS:
        return _resultado(
            is_valid_service=False,
            needs_clarification=False,
            normalized_service=service_name,
            reason="non_service_text",
            domain_resolution_status="rejected",
        )

    if raw_normalizado in _GENERICOS_DIRECTOS or service_normalizado in _GENERICOS_DIRECTOS:
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
            clarification_question="Escribe el servicio o especialidad exacta que realmente ofreces.",
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
        domain_resolution_status="catalog_review_required",
        confidence=0.55,
    )


async def validar_servicio_semanticamente(
    *,
    cliente_openai: Optional[Any],
    supabase: Any,
    raw_service_text: str,
    service_name: str,
    timeout: float = 8.0,
) -> Dict[str, Any]:
    """Valida si un texto representa un servicio útil y suficientemente específico."""
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
        dominios_prompt = "- sin_catalogo: usar null si no hay dominio claro"

    try:
        respuesta = await cliente_openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Valida si un texto corresponde a un servicio real ofrecido por un proveedor. "
                        "Debes distinguir entre servicio válido, servicio demasiado genérico y texto basura. "
                        "No inventes especialidades."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Texto original: {raw_service_text}\n"
                        f"Servicio normalizado visible: {service_name}\n\n"
                        f"Dominios disponibles:\n{dominios_prompt}\n\n"
                        "Responde JSON con:\n"
                        "{"
                        '"status":"accepted|clarification_required|catalog_review_required|rejected",'
                        '"normalized_service":"...",'
                        '"domain_code":"... o null",'
                        '"category_name":"... o null",'
                        '"service_summary":"...",'
                        '"confidence":0.0,'
                        '"reason":"...",'
                        '"clarification_question":"... o null"'
                        "}"
                    ),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "service_validation",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "status": {
                                "type": "string",
                                "enum": [
                                    "accepted",
                                    "clarification_required",
                                    "catalog_review_required",
                                    "rejected",
                                ],
                            },
                            "normalized_service": {"type": "string"},
                            "domain_code": {"type": ["string", "null"]},
                            "category_name": {"type": ["string", "null"]},
                            "service_summary": {"type": "string"},
                            "confidence": {"type": "number"},
                            "reason": {"type": "string"},
                            "clarification_question": {"type": ["string", "null"]},
                        },
                        "required": [
                            "status",
                            "normalized_service",
                            "domain_code",
                            "category_name",
                            "service_summary",
                            "confidence",
                            "reason",
                            "clarification_question",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            temperature=0.0,
            timeout=timeout,
        )
        contenido = (respuesta.choices[0].message.content or "").strip()
        data = json.loads(contenido)
    except Exception as exc:
        logger.warning("⚠️ No se pudo validar servicio con IA: %s", exc)
        return heuristico

    status = str(data.get("status") or "").strip().lower()
    normalized_service = str(data.get("normalized_service") or service_name).strip() or service_name
    clarification_question = data.get("clarification_question")
    domain_code = data.get("domain_code")
    category_name = data.get("category_name")
    service_summary = data.get("service_summary")
    reason = str(data.get("reason") or "ai_validation").strip() or "ai_validation"

    if status == "rejected":
        return _resultado(
            is_valid_service=False,
            needs_clarification=False,
            normalized_service=normalized_service,
            reason=reason,
            domain_resolution_status="rejected",
            confidence=float(data.get("confidence") or 0.0),
        )

    if status == "clarification_required":
        return _resultado(
            is_valid_service=False,
            needs_clarification=True,
            normalized_service=normalized_service,
            reason=reason,
            domain_resolution_status="clarification_required",
            clarification_question=str(clarification_question or _pregunta_aclaracion(normalizar_texto_para_busqueda(normalized_service))),
            domain_code=normalizar_domain_code_operativo(domain_code),
            category_name=str(category_name).strip() if category_name else None,
            service_summary=str(service_summary or "").strip() or None,
            confidence=float(data.get("confidence") or 0.0),
        )

    suggested_domain_code = normalizar_domain_code_operativo(domain_code)
    resolved_domain_code = (
        suggested_domain_code if suggested_domain_code in codigos_catalogo else None
    )

    if status == "catalog_review_required" or not resolved_domain_code:
        return _resultado(
            is_valid_service=True,
            needs_clarification=False,
            normalized_service=normalized_service,
            reason=reason if suggested_domain_code or status == "catalog_review_required" else "domain_not_resolved",
            domain_resolution_status="catalog_review_required",
            domain_code=suggested_domain_code,
            resolved_domain_code=None,
            category_name=str(category_name).strip() if category_name else None,
            service_summary=str(service_summary or "").strip() or None,
            confidence=float(data.get("confidence") or heuristico["confidence"]),
        )

    return _resultado(
        is_valid_service=True,
        needs_clarification=False,
        normalized_service=normalized_service,
        reason=reason,
        domain_resolution_status="matched",
        domain_code=resolved_domain_code,
        resolved_domain_code=resolved_domain_code,
        category_name=str(category_name).strip() if category_name else None,
        service_summary=str(service_summary or "").strip() or None,
        confidence=float(data.get("confidence") or heuristico["confidence"]),
    )
