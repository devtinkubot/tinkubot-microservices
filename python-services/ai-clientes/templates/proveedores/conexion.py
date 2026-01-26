"""Mensajes de notificación de conexión con proveedores."""

from typing import Any, Dict, Optional


def mensaje_notificacion_conexion(
    proveedor: Dict[str, Any],
    url_selfie: Optional[str] = None,
    link_chat: Optional[str] = None
) -> Dict[str, Any]:
    """Genera mensaje de notificación cuando se conecta cliente con proveedor.

    Args:
        proveedor: Diccionario con datos del proveedor (debe tener 'name').
        url_selfie: URL de la selfie del proveedor (opcional).
        link_chat: Enlace de WhatsApp para abrir chat directo (opcional).

    Returns:
        Diccionario con 'response' y opcionalmente 'media_url', 'media_type', 'media_caption'.
    """
    nombre = proveedor.get("name") or proveedor.get("full_name") or "Proveedor"

    # Línea de selfie
    if url_selfie:
        selfie_line = "📸 Selfie adjunta."
    else:
        selfie_line = "📸 Selfie no disponible por el momento."

    # Línea de link
    if link_chat:
        link_line = f"🔗 Abrir chat: {link_chat}"
    else:
        link_line = "🔗 Chat disponible via WhatsApp."

    # Mensaje base
    mensaje = (
        f"Proveedor asignado: {nombre}.\n"
        f"{selfie_line}\n"
        f"{link_line}\n\n"
        f"💬 Chat abierto para coordinar tu servicio."
    )

    payload: Dict[str, Any] = {"response": mensaje}

    # Incluir media si hay selfie
    if url_selfie:
        payload.update({
            "media_url": url_selfie,
            "media_type": "image",
            "media_caption": mensaje,
        })

    return payload
