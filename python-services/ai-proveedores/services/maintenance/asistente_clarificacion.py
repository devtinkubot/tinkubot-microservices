"""Asistencia semántica para clarificar servicios genéricos o ambiguos."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from config.configuracion import configuracion
from infrastructure.database import run_supabase
from services.maintenance.clasificacion_semantica import (
    normalizar_domain_code_operativo,
)
from utils import normalizar_texto_para_busqueda

logger = logging.getLogger(__name__)

_CLARIFICATION_SIMILARITY_THRESHOLD = 0.78
_CLARIFICATION_MATCH_COUNT = 8


def _texto_limpio(valor: Any) -> Optional[str]:
    texto = str(valor or "").strip()
    return texto or None


async def _generar_embedding_consulta(
    *,
    texto: str,
    servicio_embeddings: Any = None,
    cliente_openai: Any = None,
) -> Optional[List[float]]:
    if not texto:
        return None

    if servicio_embeddings and hasattr(servicio_embeddings, "generar_embedding"):
        try:
            return await servicio_embeddings.generar_embedding(texto)
        except Exception as exc:
            logger.warning(
                "⚠️ No se pudo generar embedding con servicio local: %s",
                exc,
            )

    if cliente_openai and hasattr(cliente_openai, "embeddings"):
        try:
            respuesta = await cliente_openai.embeddings.create(
                model=configuracion.modelo_embeddings,
                input=texto,
            )
            return list(respuesta.data[0].embedding)
        except Exception as exc:
            logger.warning(
                "⚠️ No se pudo generar embedding directo con OpenAI: %s",
                exc,
            )

    return None


async def _buscar_similares(
    *,
    supabase: Any,
    embedding: List[float],
    match_count: int,
) -> List[Dict[str, Any]]:
    respuesta = await run_supabase(
        lambda: supabase.rpc(
            "match_provider_services",
            {
                "query_embedding": embedding,
                "match_count": match_count,
                "city_filter": None,
                "similarity_threshold": _CLARIFICATION_SIMILARITY_THRESHOLD,
            },
        ).execute(),
        label="provider_services.clarification_examples",
    )
    return list(getattr(respuesta, "data", None) or [])


def _extraer_ejemplo(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    service_name = (
        _texto_limpio(row.get("matched_service_name"))
        or _texto_limpio(row.get("service_name"))
        or _texto_limpio(row.get("service_name_normalized"))
    )
    if not service_name:
        return None

    service_summary = _texto_limpio(
        row.get("matched_service_summary")
    ) or _texto_limpio(row.get("service_summary"))
    domain_code = normalizar_domain_code_operativo(row.get("domain_code"))
    category_name = _texto_limpio(row.get("category_name"))
    distance_raw = row.get("distance")
    similarity_score = None
    try:
        if distance_raw is not None:
            similarity_score = max(0.0, min(1.0, 1.0 - float(distance_raw)))
    except (TypeError, ValueError):
        similarity_score = None

    return {
        "service_name": service_name,
        "service_summary": service_summary,
        "domain_code": domain_code,
        "category_name": category_name,
        "similarity_score": similarity_score,
        "raw_distance": distance_raw,
    }


def _deduplicar_ejemplos(
    ejemplos: List[Dict[str, Any]],
    *,
    limite: int,
) -> List[Dict[str, Any]]:
    vistos: set[str] = set()
    resultado: List[Dict[str, Any]] = []
    for ejemplo in ejemplos:
        clave = normalizar_texto_para_busqueda(ejemplo.get("service_name") or "")
        if not clave or clave in vistos:
            continue
        vistos.add(clave)
        resultado.append(ejemplo)
        if len(resultado) >= limite:
            break
    return resultado


def _formatear_linea_ejemplo(indice: int, ejemplo: Dict[str, Any]) -> str:
    service_name = str(ejemplo.get("service_name") or "").strip()
    category_name = str(ejemplo.get("category_name") or "").strip()
    service_summary = str(ejemplo.get("service_summary") or "").strip()

    linea = f"{indice}. {service_name}"
    if category_name:
        linea += f" ({category_name})"
    if service_summary:
        linea += f" - {service_summary}"
    return linea


async def construir_mensaje_clarificacion_servicio(
    *,
    supabase: Any,
    servicio_embeddings: Any = None,
    cliente_openai: Any = None,
    raw_service_text: str,
    service_name: str,
    clarification_question: Optional[str] = None,
    service_summary: Optional[str] = None,
    domain_code: Optional[str] = None,
    category_name: Optional[str] = None,
    max_examples: int = 3,
) -> Dict[str, Any]:
    """Construye un mensaje guía con ejemplos reales cercanos."""
    question = _texto_limpio(clarification_question) or (
        "Indica el servicio o especialidad exacta que ofreces."
    )
    max_examples = max(1, min(int(max_examples or 3), 5))

    partes_consulta = [
        _texto_limpio(raw_service_text),
        _texto_limpio(service_name),
        _texto_limpio(service_summary),
        normalizar_domain_code_operativo(domain_code),
        _texto_limpio(category_name),
    ]
    texto_consulta = " ".join(
        parte for parte in partes_consulta if parte and parte.lower() not in {"null"}
    ).strip()
    embedding = await _generar_embedding_consulta(
        texto=texto_consulta or service_name or raw_service_text,
        servicio_embeddings=servicio_embeddings,
        cliente_openai=cliente_openai,
    )

    ejemplos: List[Dict[str, Any]] = []
    if supabase and embedding:
        try:
            filas = await _buscar_similares(
                supabase=supabase,
                embedding=embedding,
                match_count=max(_CLARIFICATION_MATCH_COUNT, max_examples * 3),
            )
            candidatos = []
            for fila in filas:
                ejemplo = _extraer_ejemplo(fila)
                if ejemplo:
                    candidatos.append(ejemplo)
            ejemplos = _deduplicar_ejemplos(candidatos, limite=max_examples)
        except Exception as exc:
            logger.warning("⚠️ No se pudieron obtener ejemplos cercanos: %s", exc)

    lineas = [question]
    if ejemplos:
        lineas.append("")
        lineas.append("Para ayudarte a aterrizarlo, estos servicios reales se parecen:")
        for idx, ejemplo in enumerate(ejemplos, start=1):
            lineas.append(_formatear_linea_ejemplo(idx, ejemplo))
        lineas.append("")
        lineas.append(
            "Respóndeme con una versión más específica o cuéntame qué hace "
            "exactamente el cliente para pedirte ese servicio."
        )
    else:
        lineas.append("")
        lineas.append(
            "Respóndeme con un caso concreto, el tipo de cliente o el problema "
            "exacto que resuelves."
        )
        lineas.append(
            "Si quieres, menciona el servicio como lo buscaría un cliente en "
            "WhatsApp."
        )

    return {
        "message": "\n".join(lineas).strip(),
        "examples": ejemplos,
        "embedding_used": bool(embedding),
        "clarification_question": question,
    }
