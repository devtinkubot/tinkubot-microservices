"""Catálogo y validación semántica local para onboarding."""

from __future__ import annotations

import json
import logging
import re
import os
import unicodedata
from typing import Any, Dict, List, Optional

from config.configuracion import configuracion
from infrastructure.database import run_supabase
from services.shared.prompts_ia import (
    construir_prompt_sistema_enriquecimiento_servicios,
    construir_prompt_usuario_enriquecimiento_servicios,
    construir_prompt_sistema_sugerencia_revision_catalogo,
    construir_prompt_usuario_sugerencia_revision_catalogo,
)
from utils import normalizar_texto_para_busqueda

logger = logging.getLogger(__name__)

SERVICIOS_MAXIMOS_ONBOARDING = int(os.getenv("PROVIDER_ONBOARDING_MAX_SERVICES", "10"))
DISPLAY_ORDER_MAX_DB = int(os.getenv("PROVIDER_SERVICES_DISPLAY_ORDER_MAX", "6"))

_DOMAIN_CODE_ALIASES = {
    "alimentacion": "gastronomia_alimentos",
    "gastronomia": "gastronomia_alimentos",
    "cuidado_personal": "cuidados_asistencia",
    "educacion": "academico",
    "entretenimiento": "eventos",
    "medio_ambiente": "servicios_administrativos",
}
_DOMAIN_DISPLAY_NAME_OVERRIDES = {
    "construccion_hogar": "Construcción",
    "cuidados_asistencia": "Cuidados",
    "gastronomia_alimentos": "Gastronomía",
    "servicios_administrativos": "Administración",
}
_DOMAIN_DISPLAY_NAME_STOPWORDS = {
    "y",
    "de",
    "del",
    "la",
    "el",
    "los",
    "las",
    "para",
    "en",
    "con",
}
_VALORES_NULOS = {"", "null", "none", "nil", "n/a", "na"}


def _normalizar_codigo(texto: Optional[str]) -> Optional[str]:
    base = unicodedata.normalize("NFD", str(texto or "").strip().lower())
    sin_acentos = "".join(ch for ch in base if unicodedata.category(ch) != "Mn")
    valor = re.sub(r"[^a-z0-9]+", "_", sin_acentos).strip("_")
    return valor or None


def normalizar_domain_code_operativo(texto: Optional[str]) -> Optional[str]:
    code = _normalizar_codigo(texto)
    if not code:
        return None
    return _DOMAIN_CODE_ALIASES.get(code, code)


def normalizar_display_name_dominio(
    domain_code: Optional[str],
    display_name: Optional[str] = None,
) -> str:
    code = normalizar_domain_code_operativo(domain_code)
    texto_visible = " ".join(str(display_name or "").split())
    if code in _DOMAIN_DISPLAY_NAME_OVERRIDES:
        return _DOMAIN_DISPLAY_NAME_OVERRIDES[code]
    if texto_visible:
        palabras_visibles = [palabra for palabra in texto_visible.split() if palabra]
        if len(texto_visible) <= 24:
            return " ".join(
                palabra[:1].upper() + palabra[1:] for palabra in palabras_visibles
            )
    if not code:
        return texto_visible[:24].strip()
    palabras_codigo = [
        palabra
        for palabra in code.split("_")
        if palabra and palabra not in _DOMAIN_DISPLAY_NAME_STOPWORDS
    ]
    if not palabras_codigo:
        palabras_codigo = [code]
    if len(palabras_codigo) > 2:
        palabras_codigo = palabras_codigo[:2]
    candidato = " ".join(
        palabra[:1].upper() + palabra[1:] for palabra in palabras_codigo
    ).strip()
    if len(candidato) <= 24:
        return candidato
    return (palabras_codigo[0][:1].upper() + palabras_codigo[0][1:]).strip()


def construir_service_summary(
    *,
    service_name: str,
    category_name: Optional[str] = None,
    domain_code: Optional[str] = None,
) -> str:
    service = str(service_name or "").strip()
    category = str(category_name or "").strip().rstrip(".")
    domain = normalizar_domain_code_operativo(domain_code)
    service_lower = service.lower()
    category_lower = category.lower() if category else ""

    if not service:
        return ""
    if domain == "legal":
        if service_lower.startswith("asesoria legal en "):
            area = service_lower.removeprefix("asesoria legal en ").strip()
            return f"Brindo orientación y acompañamiento en temas de {area}."
        if service_lower.startswith("asesoria en "):
            area = service_lower.removeprefix("asesoria en ").strip()
            return f"Brindo orientación y acompañamiento en {area}."
        if "derecho" in service_lower:
            return f"Atiendo casos y trámites relacionados con {service_lower}."
        return f"Brindo asesoría y acompañamiento en {service_lower}."
    if domain == "tecnologia":
        return f"Desarrollo, implemento o doy soporte en {service_lower}, según lo que necesite el cliente."
    if domain == "construccion_hogar":
        return f"Realizo trabajos de {service_lower} para viviendas, negocios u otros espacios."
    if domain == "salud":
        return f"Atiendo necesidades de salud relacionadas con {service_lower}."
    if domain == "transporte":
        return f"Realizo traslados y trabajos de {service_lower}, según el tipo de carga, ruta o necesidad."
    if domain == "vehiculos":
        return f"Trabajo en {service_lower} para diagnóstico, mantenimiento o solución de problemas del vehículo."
    if domain == "servicios_administrativos":
        if service_lower.startswith("consultoria en "):
            area = service_lower.removeprefix("consultoria en ").strip()
            return "Apoyo a negocios y organizaciones con consultoría en " + area + " para ordenar, mejorar o gestionar procesos."
        if service_lower.startswith("consultoria "):
            return "Apoyo a negocios y organizaciones con " + service_lower + " para ordenar, mejorar o gestionar procesos."
        return f"Apoyo en {service_lower} para ordenar, mejorar o gestionar procesos del negocio."
    if domain == "gastronomia_alimentos":
        return f"Ofrezco {service_lower} para eventos, negocios o consumo diario, según lo que se requiera."
    if domain == "academico":
        return f"Brindo apoyo en {service_lower} para reforzar aprendizaje, tareas o formación."
    if domain == "marketing":
        if service_lower == "marketing digital":
            return "Apoyo a negocios con marketing digital para conseguir más visibilidad, clientes y ventas."
        return f"Apoyo con {service_lower} para mejorar visibilidad, promoción y resultados comerciales."
    if domain == "cuidados_asistencia":
        return f"Brindo apoyo y acompañamiento en {service_lower}, según la necesidad de la persona o familia."
    if domain == "eventos":
        return f"Apoyo con {service_lower} para la organización, atención o desarrollo de eventos."
    if domain == "inmobiliario":
        return f"Brindo apoyo en {service_lower} para alquiler, venta, búsqueda o gestión de inmuebles."
    if domain == "financiero":
        return f"Apoyo con {service_lower} para control, análisis o toma de decisiones financieras."
    if domain == "belleza":
        return f"Realizo {service_lower} para cuidado personal, imagen y bienestar."
    if category and category_lower not in service_lower:
        return f"Trabajo en {category_lower} con enfoque en {service_lower}."
    return f"Ofrezco {service_lower} según la necesidad del cliente."


def construir_texto_embedding_canonico(
    *,
    service_name_normalized: str,
    domain_code: Optional[str] = None,
    category_name: Optional[str] = None,
) -> str:
    componentes: List[str] = []
    nombre_normalizado = normalizar_texto_para_busqueda(service_name_normalized)
    if nombre_normalizado:
        componentes.append(nombre_normalizado)
    domain = normalizar_domain_code_operativo(domain_code)
    if domain:
        componentes.append(domain)
    category = normalizar_texto_para_busqueda(category_name)
    if category:
        componentes.append(category)
    return " | ".join(componentes)


async def obtener_catalogo_dominios_liviano(supabase: Any) -> List[Dict[str, str]]:
    if not supabase:
        return []
    try:
        respuesta = await run_supabase(
            lambda: supabase.table("service_domains")
            .select("code,display_name,description,status")
            .order("code", desc=False)
            .execute(),
            label="service_domains.light_catalog.onboarding",
        )
        data = getattr(respuesta, "data", None) or []
    except Exception as exc:
        logger.warning("⚠️ No se pudo leer catálogo de dominios: %s", exc)
        return []
    catalogo: List[Dict[str, str]] = []
    for item in data:
        code = normalizar_domain_code_operativo(item.get("code"))
        display_name = normalizar_display_name_dominio(
            code,
            item.get("display_name"),
        )
        if code and display_name:
            catalogo.append(
                {
                    "code": code,
                    "display_name": display_name,
                    "description": str(item.get("description") or "").strip(),
                    "status": str(item.get("status") or "").strip(),
                }
            )
    return catalogo


async def clasificar_servicios_livianos(
    *,
    cliente_openai: Optional[Any],
    supabase: Any,
    servicios: List[str],
    timeout: float = 8.0,
) -> List[Dict[str, Any]]:
    servicios_limpios = [
        str(servicio).strip() for servicio in servicios if str(servicio).strip()
    ]
    if not servicios_limpios:
        return []

    fallback = [
        {
            "normalized_service": servicio,
            "domain_code": None,
            "resolved_domain_code": None,
            "domain_resolution_status": "catalog_review_required",
            "category_name": None,
            "proposed_category_name": None,
            "service_summary": construir_service_summary(service_name=servicio),
            "proposed_service_summary": construir_service_summary(
                service_name=servicio
            ),
            "classification_confidence": 0.0,
        }
        for servicio in servicios_limpios
    ]
    if not cliente_openai:
        return fallback

    catalogo_dominios = await obtener_catalogo_dominios_liviano(supabase)
    codigos_catalogo = {
        item["code"] for item in catalogo_dominios if item.get("code")
    }

    resultados: List[Dict[str, Any]] = []
    for servicio in servicios_limpios:
        try:
            fila = await validar_servicio_semanticamente(
                cliente_openai=cliente_openai,
                supabase=supabase,
                raw_service_text=servicio,
                service_name=servicio,
                timeout=timeout,
            )
        except Exception as exc:
            logger.warning("⚠️ No se pudo enriquecer servicio '%s': %s", servicio, exc)
            fila = {}

        normalized_service_visible = str(
            fila.get("normalized_service") or servicio
        ).strip() or servicio
        normalized_domain = normalizar_domain_code_operativo(
            fila.get("resolved_domain_code") or fila.get("domain_code")
        )
        resolved_domain_code = (
            normalized_domain if normalized_domain in codigos_catalogo else None
        )
        category_name = (
            str(fila.get("proposed_category_name") or fila.get("category_name") or "")
            .strip()
            or None
        )
        service_summary = (
            str(
                fila.get("proposed_service_summary") or fila.get("service_summary") or ""
            ).strip()
            or construir_service_summary(
                service_name=normalized_service_visible,
                category_name=category_name,
                domain_code=normalized_domain,
            )
        )
        confidence = max(0.0, min(1.0, float(fila.get("confidence") or 0.0)))
        resultados.append(
            {
                "normalized_service": normalized_service_visible,
                "domain_code": normalized_domain,
                "resolved_domain_code": resolved_domain_code,
                "domain_resolution_status": (
                    fila.get("domain_resolution_status")
                    if fila.get("domain_resolution_status")
                    else (
                        "matched"
                        if resolved_domain_code
                        else "catalog_review_required"
                    )
                ),
                "category_name": category_name,
                "proposed_category_name": category_name,
                "service_summary": service_summary,
                "proposed_service_summary": service_summary,
                "classification_confidence": confidence,
            }
        )
    return resultados


def _codigos_catalogo(catalogo_dominios: Optional[list[Dict[str, str]]]) -> set[str]:
    return {
        code
        for code in (
            normalizar_domain_code_operativo(item.get("code"))
            for item in (catalogo_dominios or [])
        )
        if code
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
        "proposed_category_name": category_name,
        "proposed_service_summary": proposed_summary,
        "confidence": max(0.0, min(1.0, float(confidence))),
        "reason": reason,
        "clarification_question": clarification_question,
    }


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


def _validacion_heuristica(
    *,
    raw_service_text: str,
    service_name: str,
) -> Dict[str, Any]:
    from utils import limpiar_texto_servicio

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
    heuristico = _validacion_heuristica(
        raw_service_text=raw_service_text,
        service_name=service_name,
    )
    if not heuristico["is_valid_service"] or heuristico["needs_clarification"]:
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
        dominios_prompt = "- sin_catalogo: usar la opción más cercana si no hay catálogo útil"

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
                        raw_service_text=raw_service_text,
                        service_name=service_name,
                        dominios_prompt=dominios_prompt,
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
                            "is_valid_service": {"type": "boolean"},
                            "needs_clarification": {"type": "boolean"},
                            "normalized_service": {"type": "string"},
                            "domain_code": {"type": ["string", "null"]},
                            "resolved_domain_code": {"type": ["string", "null"]},
                            "category_name": {"type": ["string", "null"]},
                            "service_summary": {"type": ["string", "null"]},
                            "confidence": {"type": "number"},
                            "reason": {"type": "string"},
                            "clarification_question": {"type": ["string", "null"]},
                        },
                        "required": [
                            "is_valid_service",
                            "needs_clarification",
                            "normalized_service",
                            "domain_code",
                            "resolved_domain_code",
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
            temperature=configuracion.openai_temperature_consistente,
            timeout=timeout,
        )
        contenido = (respuesta.choices[0].message.content or "").strip()
        data = json.loads(contenido)
    except Exception as exc:
        logger.warning("⚠️ No se pudo validar semánticamente el servicio: %s", exc)
        return heuristico

    if not data.get("is_valid_service"):
        return _resultado(
            is_valid_service=False,
            needs_clarification=bool(data.get("needs_clarification")),
            normalized_service=str(data.get("normalized_service") or service_name),
            reason=str(data.get("reason") or "service_rejected"),
            domain_resolution_status="rejected",
            clarification_question=data.get("clarification_question"),
            domain_code=data.get("domain_code"),
            resolved_domain_code=data.get("resolved_domain_code"),
            category_name=data.get("category_name"),
            service_summary=data.get("service_summary"),
            confidence=float(data.get("confidence") or 0.0),
        )

    resolved_domain = normalizar_domain_code_operativo(data.get("resolved_domain_code"))
    if resolved_domain and codigos_catalogo and resolved_domain not in codigos_catalogo:
        resolved_domain = None

    return _resultado(
        is_valid_service=True,
        needs_clarification=bool(data.get("needs_clarification")),
        normalized_service=str(data.get("normalized_service") or service_name),
        reason=str(data.get("reason") or "service_validated"),
        domain_resolution_status="catalog_review_required" if resolved_domain else "heuristic_accept",
        clarification_question=data.get("clarification_question"),
        domain_code=data.get("domain_code"),
        resolved_domain_code=resolved_domain,
        category_name=data.get("category_name"),
        service_summary=data.get("service_summary"),
        confidence=float(data.get("confidence") or 0.0),
    )


async def generar_sugerencia_revision_catalogo_servicio(
    *,
    cliente_openai: Any,
    raw_service_text: str,
    service_name: str,
    dominios_catalogo: List[Dict[str, str]],
    timeout: float = 8.0,
) -> Dict[str, Any]:
    service_name_limpio = _texto_opcional(service_name) or _texto_opcional(raw_service_text)
    raw_service_text_limpio = _texto_opcional(raw_service_text) or service_name_limpio
    if not service_name_limpio:
        return {
            "suggested_domain_code": None,
            "proposed_category_name": None,
            "proposed_service_summary": None,
            "review_reason": "empty_service_review",
            "confidence": 0.0,
        }

    dominios_prompt = "\n".join(
        f"- {item['code']}: {item['display_name']}"
        + (f" ({item['description']})" if item.get("description") else "")
        for item in dominios_catalogo[:40]
        if item.get("code") and item.get("display_name")
    ) or "- sin_catalogo: usar la opción más cercana si no hay catálogo útil"

    try:
        respuesta = await cliente_openai.chat.completions.create(
            model=configuracion.openai_chat_model,
            messages=[
                {
                    "role": "system",
                    "content": construir_prompt_sistema_sugerencia_revision_catalogo(),
                },
                {
                    "role": "user",
                    "content": construir_prompt_usuario_sugerencia_revision_catalogo(
                        raw_service_text=raw_service_text_limpio or service_name_limpio,
                        service_name=service_name_limpio,
                        dominios_prompt=dominios_prompt,
                    ),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "service_catalog_review_suggestion",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "suggested_domain_code": {"type": ["string", "null"]},
                            "proposed_category_name": {"type": ["string", "null"]},
                            "proposed_service_summary": {"type": "string"},
                            "review_reason": {"type": "string"},
                            "confidence": {"type": "number"},
                        },
                        "required": [
                            "suggested_domain_code",
                            "proposed_category_name",
                            "proposed_service_summary",
                            "review_reason",
                            "confidence",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            temperature=configuracion.openai_temperature_consistente,
            timeout=timeout,
        )
        contenido = (respuesta.choices[0].message.content or "").strip()
        data = json.loads(contenido)
    except Exception as exc:
        logger.warning("⚠️ No se pudo generar sugerencia de catálogo: %s", exc)
        data = {}

    suggestion = {
        "suggested_domain_code": _texto_opcional(data.get("suggested_domain_code")),
        "proposed_category_name": _texto_opcional(data.get("proposed_category_name")),
        "proposed_service_summary": _texto_opcional(data.get("proposed_service_summary")),
        "review_reason": _texto_opcional(data.get("review_reason")),
        "confidence": max(0.0, min(1.0, float(data.get("confidence") or 0.0))),
    }

    if not suggestion["proposed_category_name"] or not suggestion["suggested_domain_code"]:
        basica = _inferir_sugerencia_basica(
            service_name=service_name_limpio,
            raw_service_text=raw_service_text_limpio or service_name_limpio,
            dominios_catalogo=dominios_catalogo,
        )
        suggestion["suggested_domain_code"] = suggestion["suggested_domain_code"] or basica["suggested_domain_code"]
        suggestion["proposed_category_name"] = suggestion["proposed_category_name"] or basica["proposed_category_name"]
        suggestion["review_reason"] = suggestion["review_reason"] or basica["review_reason"]
        suggestion["confidence"] = max(suggestion["confidence"], float(basica["confidence"] or 0.0))

    if not suggestion["proposed_service_summary"]:
        dominio = normalizar_domain_code_operativo(suggestion["suggested_domain_code"])
        categoria = suggestion["proposed_category_name"]
        if dominio == "tecnologia":
            suggestion["proposed_service_summary"] = f"Apoyo en {service_name_limpio.lower()} con enfoque tecnológico."
        elif dominio:
            suggestion["proposed_service_summary"] = f"Servicio de {service_name_limpio.lower()} relacionado con {dominio.replace('_', ' ')}."
        elif categoria:
            suggestion["proposed_service_summary"] = f"Servicio de {service_name_limpio.lower()} para la categoría {categoria.lower()}."
        else:
            suggestion["proposed_service_summary"] = f"Servicio relacionado con {service_name_limpio.lower()}."

    if not suggestion["review_reason"]:
        suggestion["review_reason"] = "best_effort_catalog_suggestion"
    return suggestion


def _texto_opcional(valor: Any) -> Optional[str]:
    if valor is None:
        return None
    texto = " ".join(str(valor).split()).strip()
    if not texto:
        return None
    if texto.lower() in _VALORES_NULOS:
        return None
    return texto


def _dominio_a_categoria_base(
    suggested_domain_code: Optional[str],
    dominios_catalogo: List[Dict[str, str]],
) -> Optional[str]:
    dominio = normalizar_domain_code_operativo(suggested_domain_code)
    if not dominio:
        return None
    for item in dominios_catalogo:
        if item.get("code") == dominio:
            nombre = _texto_opcional(item.get("display_name"))
            if nombre:
                return nombre
    return dominio.replace("_", " ").title()


def _inferir_sugerencia_basica(
    *,
    service_name: str,
    raw_service_text: str,
    dominios_catalogo: List[Dict[str, str]],
) -> Dict[str, Optional[str] | float]:
    texto = f"{service_name} {raw_service_text}".strip().lower()
    tokens = {
        token
        for token in texto.replace("/", " ").replace("-", " ").split()
        if len(token) >= 3
    }
    preferidos = [
        ("tecnologia", {"ia", "tic", "tics", "software", "sistema", "sistemas", "app", "aplicacion", "aplicaciones", "web", "digital", "datos", "redes", "automatizacion"}),
        ("servicios_administrativos", {"gestion", "proyecto", "proyectos", "consultoria", "asesoria", "administracion", "coordinacion"}),
        ("marketing", {"marketing", "publicidad", "ventas", "redes", "sociales", "contenidos"}),
        ("eventos", {"evento", "eventos", "celebracion", "logistica"}),
        ("salud", {"salud", "clinica", "clinico", "terapia", "medico", "medica", "bienestar"}),
    ]
    for code, keywords in preferidos:
        if tokens.intersection(keywords):
            categoria = _dominio_a_categoria_base(code, dominios_catalogo) or code.replace("_", " ").title()
            return {
                "suggested_domain_code": code,
                "proposed_category_name": categoria,
                "proposed_service_summary": None,
                "review_reason": "heuristic_best_effort_suggestion",
                "confidence": 0.35,
            }
    fallback_domain = dominios_catalogo[0]["code"] if dominios_catalogo and dominios_catalogo[0].get("code") else None
    fallback_category = _dominio_a_categoria_base(fallback_domain, dominios_catalogo)
    return {
        "suggested_domain_code": fallback_domain,
        "proposed_category_name": fallback_category,
        "proposed_service_summary": None,
        "review_reason": "heuristic_best_effort_suggestion",
        "confidence": 0.2,
    }


async def registrar_revision_catalogo_servicio(
    *,
    supabase: Any,
    provider_id: Optional[str],
    raw_service_text: str,
    service_name: str,
    suggested_domain_code: Optional[str],
    proposed_category_name: Optional[str],
    proposed_service_summary: Optional[str],
    review_reason: str,
    source: str,
) -> Optional[Dict[str, Any]]:
    if not supabase:
        return None

    payload = {
        "provider_id": provider_id,
        "raw_service_text": _texto_opcional(raw_service_text) or _texto_opcional(service_name) or "",
        "service_name": _texto_opcional(service_name) or _texto_opcional(raw_service_text) or "",
        "service_name_normalized": normalizar_texto_para_busqueda(
            _texto_opcional(service_name) or _texto_opcional(raw_service_text) or ""
        ),
        "suggested_domain_code": normalizar_domain_code_operativo(
            _texto_opcional(suggested_domain_code)
        ),
        "proposed_category_name": _texto_opcional(proposed_category_name),
        "proposed_service_summary": _texto_opcional(proposed_service_summary),
        "review_reason": _texto_opcional(review_reason) or "catalog_review_required",
        "review_status": "pending",
        "source": _texto_opcional(source) or "provider_onboarding",
    }

    try:
        review_key = {
            "provider_id": provider_id,
            "service_name_normalized": payload["service_name_normalized"],
            "source": payload["source"],
            "review_status": "pending",
        }
        existing_response = await run_supabase(
            lambda: supabase.table("provider_service_catalog_reviews")
            .select("id")
            .match(review_key)
            .limit(1)
            .execute(),
            label="provider_service_catalog_reviews.find_pending_duplicate.onboarding",
        )
        existing_rows = getattr(existing_response, "data", None) or []
        if existing_rows:
            review_id = existing_rows[0].get("id")
            if review_id:
                respuesta = await run_supabase(
                    lambda: supabase.table("provider_service_catalog_reviews")
                    .update(payload)
                    .eq("id", review_id)
                    .execute(),
                    label="provider_service_catalog_reviews.update_pending.onboarding",
                )
                filas = getattr(respuesta, "data", None) or []
                return filas[0] if filas else {"id": review_id, **payload}

        respuesta = await run_supabase(
            lambda: supabase.table("provider_service_catalog_reviews")
            .insert(payload)
            .execute(),
            label="provider_service_catalog_reviews.insert.onboarding",
        )
    except Exception as exc:
        logger.warning("⚠️ No se pudo registrar revisión de catálogo: %s", exc)
        return None

    filas = getattr(respuesta, "data", None) or []
    return filas[0] if filas else None


async def eliminar_revisiones_catalogo_asociadas_servicio(
    *,
    supabase: Any,
    provider_id: Optional[str] = None,
    published_provider_service_id: Optional[str] = None,
) -> int:
    if not supabase:
        return 0

    query = supabase.table("provider_service_catalog_reviews").delete()
    filtro_aplicado = False
    if published_provider_service_id:
        query = query.eq("published_provider_service_id", published_provider_service_id)
        filtro_aplicado = True
    if provider_id:
        query = query.eq("provider_id", provider_id)
        filtro_aplicado = True
    if not filtro_aplicado:
        return 0

    try:
        respuesta = await run_supabase(
            lambda: query.execute(),
            label="provider_service_catalog_reviews.delete_associated.onboarding",
        )
    except Exception as exc:
        logger.warning("⚠️ No se pudieron eliminar reviews asociadas: %s", exc)
        return 0

    filas = getattr(respuesta, "data", None) or []
    return len(filas)
