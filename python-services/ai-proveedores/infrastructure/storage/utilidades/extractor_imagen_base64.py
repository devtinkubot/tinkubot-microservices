"""
Utilidad para extracción de imágenes en formato base64 desde payloads.
"""

from typing import Any, Dict, Optional


def extraer_primera_imagen_base64(payload: Dict[str, Any]) -> Optional[str]:
    """
    Extrae la primera imagen en formato base64 desde un payload.

    Busca imágenes en múltiples ubicaciones posibles dentro del payload:
    - Campos directos: image_base64, media_base64, file_base64
    - Arreglos de attachments/media
    - Campo content con data URI scheme

    Args:
        payload: Diccionario que puede contener una o más imágenes.

    Returns:
        Primera imagen encontrada en formato base64, o None si no se encontró ninguna.
    """
    # Buscar en campos directos
    candidates = [
        payload.get("image_base64"),
        payload.get("media_base64"),
        payload.get("file_base64"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    # Buscar en attachments o media
    attachments = payload.get("attachments") or payload.get("media") or []
    if isinstance(attachments, dict):
        attachments = [attachments]

    for item in attachments:
        if not isinstance(item, dict):
            continue

        # Verificar que sea del tipo imagen
        if item.get("type") and item["type"].lower() not in {
            "image",
            "photo",
            "picture",
        }:
            continue

        # Extraer datos base64
        data = item.get("base64") or item.get("data") or item.get("content")
        if isinstance(data, str) and data.strip():
            return data.strip()

    # Buscar en content/message con data URI scheme
    content = payload.get("content") or payload.get("message")
    if isinstance(content, str) and content.startswith("data:image/"):
        return content

    return None
