"""Mensajes de conexión con proveedores."""

from typing import Any, Dict, Optional

from infrastructure.storage import construir_url_media_publica
from templates.proveedores.conexion import mensaje_notificacion_conexion


def _construir_enlace_whatsapp(telefono: str) -> Optional[str]:
    if not telefono:
        return None

    bruto = telefono.strip()
    if bruto.endswith("@lid"):
        return None
    if bruto.endswith("@c.us"):
        bruto = bruto.replace("@c.us", "")
    bruto = bruto.lstrip("+")
    return f"https://wa.me/{bruto}"


def mensaje_conexion_formal(
    proveedor: Dict[str, Any],
    *,
    supabase,
    bucket: str,
    supabase_base_url: str,
) -> Dict[str, Any]:
    nombre = proveedor.get("name") or proveedor.get("full_name") or "Proveedor"
    telefono_bruto = (
        proveedor.get("real_phone")
        or proveedor.get("phone")
        or proveedor.get("phone_number")
    )

    link = _construir_enlace_whatsapp(telefono_bruto) if telefono_bruto else None

    selfie_url_raw = (
        proveedor.get("face_photo_url")
        or proveedor.get("selfie_url")
        or proveedor.get("photo_url")
    )
    selfie_url = (
        construir_url_media_publica(
            selfie_url_raw,
            supabase=supabase,
            bucket=bucket,
            supabase_base_url=supabase_base_url,
        )
        if selfie_url_raw
        else None
    )

    return mensaje_notificacion_conexion(
        proveedor={"name": nombre},
        url_selfie=selfie_url,
        link_chat=link,
    )
