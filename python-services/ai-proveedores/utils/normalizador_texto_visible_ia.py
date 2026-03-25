"""Normalización visible de textos apoyada por IA."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from config.configuracion import configuracion
from services.shared import (
    construir_prompt_sistema_normalizacion_visible,
    construir_prompt_usuario_normalizacion_visible,
)

from .normalizador_texto_visible import normalizar_texto_visible_corto

logger = logging.getLogger(__name__)


def _limpiar_visible(texto: str) -> str:
    return re.sub(r"[\s,;:\-]+$", "", " ".join(str(texto or "").split())).strip()


async def normalizar_texto_visible_con_ia(
    cliente_openai: Optional[Any],
    texto: str,
    maximo: int = 68,
    timeout: float = 4.0,
) -> str:
    """Pide a IA que compacte un texto a una forma natural y visible."""
    texto_visible = " ".join(str(texto or "").strip().split())
    if not texto_visible:
        return ""
    if len(texto_visible) <= maximo:
        return texto_visible
    if not cliente_openai or not hasattr(cliente_openai, "chat"):
        return normalizar_texto_visible_corto(texto_visible, maximo=maximo)

    texto_base = texto_visible
    nota_reintento = ""
    for intento in range(2):
        try:
            respuesta = await cliente_openai.chat.completions.create(
                model=configuracion.openai_chat_model,
                messages=[
                    {
                        "role": "system",
                        "content": construir_prompt_sistema_normalizacion_visible(
                            maximo
                        ),
                    },
                    {
                        "role": "user",
                        "content": construir_prompt_usuario_normalizacion_visible(
                            texto_base,
                            maximo,
                            nota_reintento=nota_reintento,
                        ),
                    },
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "visible_service_normalization",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {"normalized_service": {"type": "string"}},
                            "required": ["normalized_service"],
                            "additionalProperties": False,
                        },
                    },
                },
                temperature=configuracion.openai_temperature_precisa,
                timeout=timeout,
            )
            contenido = (respuesta.choices[0].message.content or "").strip()
            data = json.loads(contenido)
        except Exception as exc:  # pragma: no cover - red fallback
            logger.warning("⚠️ No se pudo compactar texto visible con IA: %s", exc)
            break

        candidato = _limpiar_visible(str(data.get("normalized_service") or ""))
        if candidato and len(candidato) <= maximo:
            return candidato

        if intento == 0:
            nota_reintento = (
                "Tu respuesta anterior fue demasiado larga. "
                "Acórtala todavía más y conserva el sentido. "
            )

    return normalizar_texto_visible_corto(texto_base, maximo=maximo)
