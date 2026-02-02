"""
Utilidad para extracción de imágenes en formato base64 desde cargas.
"""

from typing import Any, Dict, Optional


def extraer_primera_imagen_base64(carga: Dict[str, Any]) -> Optional[str]:
    """
    Extrae la primera imagen en formato base64 desde una carga.

    Busca imágenes en múltiples ubicaciones posibles dentro de la carga:
    - Campos directos: image_base64, media_base64, file_base64
    - Arreglos de attachments/media
    - Campo content con data URI scheme

    Args:
        carga: Diccionario que puede contener una o más imágenes.

    Returns:
        Primera imagen encontrada en formato base64, o None si no se encontró ninguna.
    """
    # Buscar en campos directos
    candidatos = [
        carga.get("image_base64"),
        carga.get("media_base64"),
        carga.get("file_base64"),
    ]
    for candidato in candidatos:
        if isinstance(candidato, str) and candidato.strip():
            return candidato.strip()

    # Buscar en attachments o media
    adjuntos = carga.get("attachments") or carga.get("media") or []
    if isinstance(adjuntos, dict):
        adjuntos = [adjuntos]

    for elemento in adjuntos:
        if not isinstance(elemento, dict):
            continue

        # Verificar que sea del tipo imagen
        if elemento.get("type") and elemento["type"].lower() not in {
            "image",
            "photo",
            "picture",
        }:
            continue

        # Extraer datos base64
        datos = elemento.get("base64") or elemento.get("data") or elemento.get("content")
        if isinstance(datos, str) and datos.strip():
            return datos.strip()

    # Buscar en content/message con data URI scheme
    contenido = carga.get("content") or carga.get("message")
    if isinstance(contenido, str) and contenido.startswith("data:image/"):
        return contenido

    return None
