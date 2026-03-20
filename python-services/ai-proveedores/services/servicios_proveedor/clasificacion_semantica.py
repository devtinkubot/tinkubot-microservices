"""Clasificación semántica liviana para servicios de proveedores."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional

from infrastructure.database import run_supabase
from services.servicios_proveedor.utilidades import (
    normalizar_texto_visible_con_ia,
)

logger = logging.getLogger(__name__)

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


def _normalizar_codigo(texto: Optional[str]) -> Optional[str]:
    base = unicodedata.normalize("NFD", str(texto or "").strip().lower())
    sin_acentos = "".join(ch for ch in base if unicodedata.category(ch) != "Mn")
    valor = re.sub(r"[^a-z0-9]+", "_", sin_acentos).strip("_")
    return valor or None


def normalizar_domain_code_operativo(texto: Optional[str]) -> Optional[str]:
    """Mapea dominios libres o legacy al catálogo operativo final."""
    code = _normalizar_codigo(texto)
    if not code:
        return None
    return _DOMAIN_CODE_ALIASES.get(code, code)


def normalizar_display_name_dominio(
    domain_code: Optional[str],
    display_name: Optional[str] = None,
) -> str:
    """Normaliza el nombre visible de un dominio para que entre en la lista."""
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


def construir_service_summary(  # noqa: C901
    *,
    service_name: str,
    category_name: Optional[str] = None,
    domain_code: Optional[str] = None,
) -> str:
    """Genera un resumen corto y operativo del servicio."""
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
        return (
            "Desarrollo, implemento o doy soporte en "
            f"{service_lower}, según lo que necesite el cliente."
        )

    if domain == "construccion_hogar":
        return (
            f"Realizo trabajos de {service_lower} para viviendas, "
            "negocios u otros espacios."
        )

    if domain == "salud":
        return f"Atiendo necesidades de salud relacionadas con {service_lower}."

    if domain == "transporte":
        return (
            f"Realizo traslados y trabajos de {service_lower}, "
            "según el tipo de carga, ruta o necesidad."
        )

    if domain == "vehiculos":
        return (
            f"Trabajo en {service_lower} para diagnóstico, mantenimiento "
            "o solución de problemas del vehículo."
        )

    if domain == "servicios_administrativos":
        if service_lower.startswith("consultoria en "):
            area = service_lower.removeprefix("consultoria en ").strip()
            return (
                "Apoyo a negocios y organizaciones con consultoría en "
                f"{area} para ordenar, mejorar o gestionar procesos."
            )
        if service_lower.startswith("consultoria "):
            return (
                "Apoyo a negocios y organizaciones con "
                f"{service_lower} para ordenar, mejorar o gestionar procesos."
            )
        return (
            f"Apoyo en {service_lower} para ordenar, mejorar o gestionar "
            "procesos del negocio."
        )

    if domain == "gastronomia_alimentos":
        return (
            f"Ofrezco {service_lower} para eventos, negocios o consumo "
            "diario, según lo que se requiera."
        )

    if domain == "academico":
        return (
            f"Brindo apoyo en {service_lower} para reforzar aprendizaje, "
            "tareas o formación."
        )

    if domain == "marketing":
        if service_lower == "marketing digital":
            return (
                "Apoyo a negocios con marketing digital para conseguir más "
                "visibilidad, clientes y ventas."
            )
        return (
            f"Apoyo con {service_lower} para mejorar visibilidad, "
            "promoción y resultados comerciales."
        )

    if domain == "cuidados_asistencia":
        return (
            f"Brindo apoyo y acompañamiento en {service_lower}, según la "
            "necesidad de la persona o familia."
        )

    if domain == "eventos":
        return (
            f"Apoyo con {service_lower} para la organización, atención o "
            "desarrollo de eventos."
        )

    if domain == "inmobiliario":
        return (
            f"Brindo apoyo en {service_lower} para alquiler, venta, "
            "búsqueda o gestión de inmuebles."
        )

    if domain == "financiero":
        return (
            f"Apoyo con {service_lower} para control, análisis o toma de "
            "decisiones financieras."
        )

    if domain == "belleza":
        return f"Realizo {service_lower} para cuidado personal, imagen y bienestar."

    if category and category_lower not in service_lower:
        return f"Trabajo en {category_lower} con enfoque en {service_lower}."

    return f"Ofrezco {service_lower} según la necesidad del cliente."


async def obtener_catalogo_dominios_liviano(supabase: Any) -> List[Dict[str, str]]:
    """Lee un catálogo liviano de dominios desde `service_domains`."""
    if not supabase:
        return []

    try:
        respuesta = await run_supabase(
            lambda: supabase.table("service_domains")
            .select("code,display_name,description,status")
            .order("code", desc=False)
            .execute(),
            label="service_domains.light_catalog",
        )
    except Exception as exc:
        logger.warning("⚠️ No se pudo cargar catálogo liviano de dominios: %s", exc)
        return []

    catalogo: List[Dict[str, str]] = []
    for fila in getattr(respuesta, "data", None) or []:
        status = str(fila.get("status") or "").strip().lower()
        if status and status not in {"active", "published"}:
            continue
        code = _normalizar_codigo(fila.get("code"))
        display_name = normalizar_display_name_dominio(
            code,
            fila.get("display_name") or fila.get("code"),
        )
        if not code or not display_name:
            continue
        catalogo.append(
            {
                "code": normalizar_domain_code_operativo(code),
                "display_name": display_name,
                "description": str(fila.get("description") or "").strip(),
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
    """
    Clasifica servicios con un catálogo liviano de dominios.

    Si la clasificación falla, se degrada a un payload mínimo sin dominio/categoría.
    """
    servicios_limpios = [
        str(servicio).strip() for servicio in servicios if str(servicio).strip()
    ]
    if not servicios_limpios:
        return []

    catalogo_dominios = await obtener_catalogo_dominios_liviano(supabase)
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

    dominios_prompt = "\n".join(
        f"- {item['code']}: {item['display_name']}"
        + (f" ({item['description']})" if item.get("description") else "")
        for item in catalogo_dominios[:40]
    )
    if not dominios_prompt:
        dominios_prompt = "- sin_catalogo: usar null si no hay dominio claro"
    codigos_catalogo = {item["code"] for item in catalogo_dominios if item.get("code")}

    try:
        respuesta = await cliente_openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Clasifica servicios ya normalizados en un dominio "
                        "liviano y una categoría corta. Además genera un resumen "
                        "breve, claro y operativo de una sola frase. No inventes "
                        "detalles innecesarios."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Servicios a clasificar:\n"
                        + "\n".join(f"- {servicio}" for servicio in servicios_limpios)
                        + "\n\nDominios disponibles:\n"
                        + dominios_prompt
                        + "\n\n"
                        + "Responde JSON con la forma "
                        + '{"services":[{"normalized_service":"...",'
                        + '"domain_code":"... o null",'
                        + '"category_name":"... o null",'
                        + '"service_summary":"...",'
                        + '"classification_confidence":0.0}]}'
                    ),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "service_semantic_classification",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "services": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "normalized_service": {"type": "string"},
                                        "domain_code": {
                                            "type": ["string", "null"],
                                        },
                                        "category_name": {
                                            "type": ["string", "null"],
                                        },
                                        "service_summary": {"type": "string"},
                                        "classification_confidence": {
                                            "type": "number",
                                        },
                                    },
                                    "required": [
                                        "normalized_service",
                                        "domain_code",
                                        "category_name",
                                        "service_summary",
                                        "classification_confidence",
                                    ],
                                    "additionalProperties": False,
                                },
                            }
                        },
                        "required": ["services"],
                        "additionalProperties": False,
                    },
                },
            },
            temperature=0.1,
            timeout=timeout,
        )
        contenido = (respuesta.choices[0].message.content or "").strip()
        data = json.loads(contenido)
        clasificadas = data.get("services") or []
    except Exception as exc:
        logger.warning("⚠️ No se pudo clasificar servicios con IA: %s", exc)
        return fallback

    resultados: List[Dict[str, Any]] = []
    for idx, servicio in enumerate(servicios_limpios):
        fila = clasificadas[idx] if idx < len(clasificadas) else {}
        normalized_service_visible = await normalizar_texto_visible_con_ia(
            cliente_openai,
            str(fila.get("normalized_service") or servicio).strip() or servicio,
        )
        resultados.append(
            {
                "normalized_service": normalized_service_visible,
                "domain_code": normalizar_domain_code_operativo(
                    fila.get("domain_code")
                ),
                "resolved_domain_code": (
                    normalizar_domain_code_operativo(fila.get("domain_code"))
                    if normalizar_domain_code_operativo(fila.get("domain_code"))
                    in codigos_catalogo
                    else None
                ),
                "domain_resolution_status": (
                    "matched"
                    if normalizar_domain_code_operativo(fila.get("domain_code"))
                    in codigos_catalogo
                    else "catalog_review_required"
                ),
                "category_name": str(fila.get("category_name") or "").strip() or None,
                "proposed_category_name": str(fila.get("category_name") or "").strip()
                or None,
                "service_summary": str(fila.get("service_summary") or "").strip()
                or construir_service_summary(
                    service_name=normalized_service_visible or servicio,
                    category_name=str(fila.get("category_name") or "").strip() or None,
                    domain_code=fila.get("domain_code"),
                ),
                "proposed_service_summary": str(
                    fila.get("service_summary") or ""
                ).strip()
                or construir_service_summary(
                    service_name=normalized_service_visible or servicio,
                    category_name=str(fila.get("category_name") or "").strip() or None,
                    domain_code=fila.get("domain_code"),
                ),
                "classification_confidence": max(
                    0.0,
                    min(1.0, float(fila.get("classification_confidence") or 0.0)),
                ),
            }
        )
    return resultados
