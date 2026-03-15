"""Mensajes de conexión con proveedores."""

from typing import Any, Dict, Optional

from templates.proveedores.conexion import mensaje_notificacion_conexion


def _construir_enlace_whatsapp(telefono: str) -> Optional[str]:
    if not telefono:
        return None

    bruto = telefono.strip()
    if bruto.endswith("@lid"):
        return None
    if bruto.endswith("@s.whatsapp.net"):
        bruto = bruto.replace("@s.whatsapp.net", "")
    if bruto.endswith("@c.us"):
        bruto = bruto.replace("@c.us", "")
    bruto = bruto.lstrip("+")
    return f"https://wa.me/{bruto}"


def _normalizar_telefono_contacto(telefono: Optional[str]) -> Optional[str]:
    link = _construir_enlace_whatsapp(telefono) if telefono else None
    if not link:
        return None
    return link.replace("https://wa.me/", "")


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

    return mensaje_notificacion_conexion(
        proveedor={"name": nombre},
        telefono_contacto=_normalizar_telefono_contacto(telefono_bruto),
    )
