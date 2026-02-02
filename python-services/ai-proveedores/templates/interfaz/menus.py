"""Mensajes relacionados con menús de proveedores."""

from typing import List
from .componentes import pie_instrucciones_respuesta_numerica

# ==================== MENSAJES ====================

MENU_PRINCIPAL_PROVEEDOR = (
    "**Menú de Proveedores**\n"
    "\n"
    f"{pie_instrucciones_respuesta_numerica}\n"
    "\n"
    "1) Registro\n"
    "2) Salir\n"
)

MENU_POST_REGISTRO_PROVEEDOR = (
    "**Menú de Proveedor**\n"
    "\n"
    f"{pie_instrucciones_respuesta_numerica}\n"
    "\n"
    "1) Gestionar servicios\n"
    "2) Actualizar selfie\n"
    "3) Actualizar redes sociales (Instagram/Facebook)\n"
    "4) Eliminar mi registro\n"
    "5) Salir\n"
)

# ==================== FUNCIONES ====================


def mensaje_menu_principal_proveedor() -> str:
    """Genera el menú principal de proveedores."""
    return f"{MENU_PRINCIPAL_PROVEEDOR}"


def mensaje_menu_post_registro_proveedor() -> str:
    """Genera el menú posterior al registro de proveedor."""
    return f"{MENU_POST_REGISTRO_PROVEEDOR}"


def mensaje_menu_servicios_proveedor(servicios: List[str], max_servicios: int) -> str:
    """Genera el menú de gestión de servicios con los servicios registrados."""
    encabezado = ["**Gestión de Servicios**", ""]

    if servicios:
        listado = ["_Servicios registrados:_"]
        listado.extend(
            [f"{idx + 1}. {servicio}" for idx, servicio in enumerate(servicios)]
        )
    else:
        listado = ["_Todavía no registras servicios._"]

    limite_texto = (
        f"(Puedes tener hasta {max_servicios} servicios activos)."
        if max_servicios
        else ""
    )

    opciones = [
        f"{pie_instrucciones_respuesta_numerica} {limite_texto}".strip(),
        "",
        "1) Agregar servicio",
        "2) Eliminar servicio",
        "3) Volver al menú principal",
    ]

    cuerpo = encabezado + listado + opciones
    return "\n".join(part for part in cuerpo if part is not None)
