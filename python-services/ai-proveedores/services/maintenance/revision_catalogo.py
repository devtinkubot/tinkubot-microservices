"""Persistencia de revisiones de catálogo para servicios válidos fuera de dominio."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from config.configuracion import configuracion
from infrastructure.database import run_supabase
from services.maintenance.clasificacion_semantica import (
    normalizar_domain_code_operativo,
)
from services.shared.prompts_ia import (
    construir_prompt_sistema_sugerencia_revision_catalogo,
    construir_prompt_usuario_sugerencia_revision_catalogo,
)
from utils import normalizar_texto_para_busqueda

logger = logging.getLogger(__name__)

_VALORES_NULOS = {"", "null", "none", "nil", "n/a", "na"}


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
            categoria = _dominio_a_categoria_base(code, dominios_catalogo) or code.replace(
                "_", " "
            ).title()
            return {
                "suggested_domain_code": code,
                "proposed_category_name": categoria,
                "proposed_service_summary": None,
                "review_reason": "heuristic_best_effort_suggestion",
                "confidence": 0.35,
            }

    fallback_domain = (
        dominios_catalogo[0]["code"]
        if dominios_catalogo and dominios_catalogo[0].get("code")
        else None
    )
    fallback_category = _dominio_a_categoria_base(fallback_domain, dominios_catalogo)
    return {
        "suggested_domain_code": fallback_domain,
        "proposed_category_name": fallback_category,
        "proposed_service_summary": None,
        "review_reason": "heuristic_best_effort_suggestion",
        "confidence": 0.2,
    }


async def generar_sugerencia_revision_catalogo_servicio(
    *,
    cliente_openai: Any,
    raw_service_text: str,
    service_name: str,
    dominios_catalogo: List[Dict[str, str]],
    timeout: float = 8.0,
) -> Dict[str, Any]:
    """Genera una sugerencia best-effort para revisión humana de catálogo."""
    service_name_limpio = _texto_opcional(service_name) or _texto_opcional(
        raw_service_text
    )
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
    )
    if not dominios_prompt:
        dominios_prompt = "- sin_catalogo: usar la opción más cercana si no hay catálogo útil"

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
                            "suggested_domain_code": {
                                "type": ["string", "null"],
                            },
                            "proposed_category_name": {
                                "type": ["string", "null"],
                            },
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
        "proposed_service_summary": _texto_opcional(
            data.get("proposed_service_summary")
        ),
        "review_reason": _texto_opcional(data.get("review_reason")),
        "confidence": max(0.0, min(1.0, float(data.get("confidence") or 0.0))),
    }

    if not suggestion["proposed_category_name"] or not suggestion["suggested_domain_code"]:
        basica = _inferir_sugerencia_basica(
            service_name=service_name_limpio,
            raw_service_text=raw_service_text_limpio or service_name_limpio,
            dominios_catalogo=dominios_catalogo,
        )
        suggestion["suggested_domain_code"] = (
            suggestion["suggested_domain_code"] or basica["suggested_domain_code"]
        )
        suggestion["proposed_category_name"] = (
            suggestion["proposed_category_name"] or basica["proposed_category_name"]
        )
        suggestion["review_reason"] = (
            suggestion["review_reason"] or basica["review_reason"]
        )
        suggestion["confidence"] = max(
            suggestion["confidence"], float(basica["confidence"] or 0.0)
        )

    if not suggestion["proposed_service_summary"]:
        dominio = normalizar_domain_code_operativo(suggestion["suggested_domain_code"])
        categoria = suggestion["proposed_category_name"]
        if dominio == "tecnologia":
            suggestion["proposed_service_summary"] = (
                f"Apoyo en {service_name_limpio.lower()} con enfoque tecnológico."
            )
        elif dominio:
            suggestion["proposed_service_summary"] = (
                f"Servicio de {service_name_limpio.lower()} relacionado con {dominio.replace('_', ' ')}."
            )
        elif categoria:
            suggestion["proposed_service_summary"] = (
                f"Servicio de {service_name_limpio.lower()} para la categoría {categoria.lower()}."
            )
        else:
            suggestion["proposed_service_summary"] = (
                f"Servicio relacionado con {service_name_limpio.lower()}."
            )

    if not suggestion["review_reason"]:
        suggestion["review_reason"] = "best_effort_catalog_suggestion"

    return suggestion


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
    """Registra un servicio entendible que aún no encaja en el catálogo operativo."""
    if not supabase:
        logger.info(
            "catalog_review_skipped_without_supabase",
            extra={
                "provider_id": provider_id,
                "service_name": service_name,
                "source": source,
            },
        )
        return None

    payload = {
        "provider_id": provider_id,
        "raw_service_text": _texto_opcional(raw_service_text)
        or _texto_opcional(service_name)
        or "",
        "service_name": _texto_opcional(service_name) or _texto_opcional(raw_service_text) or "",
        "service_name_normalized": normalizar_texto_para_busqueda(
            _texto_opcional(service_name) or _texto_opcional(raw_service_text) or ""
        ),
        "suggested_domain_code": normalizar_domain_code_operativo(
            _texto_opcional(suggested_domain_code)
        ),
        "proposed_category_name": _texto_opcional(proposed_category_name),
        "proposed_service_summary": _texto_opcional(proposed_service_summary),
        "review_reason": _texto_opcional(review_reason)
        or "catalog_review_required",
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
            label="provider_service_catalog_reviews.find_pending_duplicate",
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
                    label="provider_service_catalog_reviews.update_pending",
                )
                filas = getattr(respuesta, "data", None) or []
                return filas[0] if filas else {"id": review_id, **payload}

        respuesta = await run_supabase(
            lambda: supabase.table("provider_service_catalog_reviews")
            .insert(payload)
            .execute(),
            label="provider_service_catalog_reviews.insert",
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
    """Elimina revisiones ligadas a un servicio o proveedor dado."""
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
            label="provider_service_catalog_reviews.delete_associated",
        )
    except Exception as exc:
        logger.warning("⚠️ No se pudieron eliminar reviews asociadas: %s", exc)
        return 0

    filas = getattr(respuesta, "data", None) or []
    return len(filas)
