"""Mensajes de notificación de conexión con proveedores."""

from typing import Any, Dict, Optional

from services.proveedores.identidad import resolver_nombre_visible_proveedor


def _contacto_whatsapp(nombre: str, telefono: str) -> Dict[str, Any]:
    nombre_limpio = (nombre or "Proveedor").strip() or "Proveedor"
    telefono_limpio = (telefono or "").strip().lstrip("+")
    primer_nombre = nombre_limpio.split()[0] if nombre_limpio else "Proveedor"
    return {
        "name": {
            "formatted_name": nombre_limpio,
            "first_name": primer_nombre,
        },
        "phones": [
            {
                "phone": f"+{telefono_limpio}",
                "type": "CELL",
                "wa_id": telefono_limpio,
            }
        ],
    }


def mensaje_notificacion_conexion(
    proveedor: Dict[str, Any],
    telefono_contacto: Optional[str] = None,
) -> Dict[str, Any]:
    """Genera una tarjeta de contacto cuando se conecta cliente con experto."""
    nombre = resolver_nombre_visible_proveedor(proveedor, status="approved")
    telefono = (telefono_contacto or "").strip()
    if not telefono:
        return {
            "response": (
                f"Te comparto el contacto de *{nombre}* para que coordines tu servicio."
            )
        }
    return {
        "response": "",
        "contacts": [_contacto_whatsapp(nombre, telefono)],
    }
