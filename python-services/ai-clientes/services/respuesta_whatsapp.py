"""Utilidades para normalizar respuestas del servicio hacia wa-gateway."""

import json
from typing import Any, Dict, List, Optional


def _firma_mensaje(mensaje: Dict[str, Any]) -> str:
    return json.dumps(
        {
            "response": (mensaje.get("response") or "").strip(),
            "media_url": (mensaje.get("media_url") or "").strip(),
            "media_type": (mensaje.get("media_type") or "").strip(),
            "media_caption": (mensaje.get("media_caption") or "").strip(),
            "ui": mensaje.get("ui"),
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def _deduplicar_mensajes_adyacentes(
    mensajes: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    deduplicados: List[Dict[str, Any]] = []
    ultima_firma: Optional[str] = None
    for mensaje in mensajes:
        firma_actual = _firma_mensaje(mensaje)
        if firma_actual == ultima_firma:
            continue
        deduplicados.append(mensaje)
        ultima_firma = firma_actual
    return deduplicados


def normalizar_respuesta_whatsapp(respuesta: Any) -> Dict[str, Any]:
    """Normaliza la respuesta para que siempre use el esquema esperado por wa-gateway."""
    if respuesta is None:
        return {"success": True, "messages": []}

    if not isinstance(respuesta, dict):
        return {"success": True, "messages": [{"response": str(respuesta)}]}

    if "messages" in respuesta:
        normalizada = dict(respuesta)
        normalizada["messages"] = _deduplicar_mensajes_adyacentes(
            list(normalizada.get("messages") or [])
        )
        if "success" not in normalizada:
            normalizada["success"] = True
        return normalizada

    if "response" in respuesta:
        texto = respuesta.get("response")
        mensajes = []
        if isinstance(texto, list):
            for item in texto:
                if isinstance(item, dict) and "response" in item:
                    mensajes.append(item)
                else:
                    mensajes.append({"response": str(item)})
        else:
            mensajes.append({"response": str(texto) if texto is not None else ""})

        normalizada = {k: v for k, v in respuesta.items() if k != "response"}
        normalizada["messages"] = _deduplicar_mensajes_adyacentes(mensajes)
        if "success" not in normalizada:
            normalizada["success"] = True
        return normalizada

    if "success" not in respuesta:
        respuesta["success"] = True
    return respuesta
