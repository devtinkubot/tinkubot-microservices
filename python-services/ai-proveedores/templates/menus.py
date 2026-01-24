"""Mensajes relacionados con menús de proveedores."""

from typing import List
from templates.comunes import pie_instrucciones_respuesta_numerica

# ==================== MENSAJES ====================

PROVIDER_MAIN_MENU = (
    "**Menú de Proveedores**\n"
    "\n"
    f"{pie_instrucciones_respuesta_numerica}\n"
    "\n"
    "1) Registro\n"
    "2) Salir\n"
)

PROVIDER_POST_REGISTRATION_MENU = (
    "**Menú de Proveedor**\n"
    "\n"
    f"{pie_instrucciones_respuesta_numerica}\n"
    "\n"
    "1) Gestionar servicios\n"
    "2) Actualizar selfie\n"
    "3) Actualizar redes sociales (Instagram/Facebook)\n"
    "4) Salir\n"
)

# ==================== FUNCIONES ====================


def provider_main_menu_message() -> str:
    """Genera el menú principal de proveedores."""
    return f"{PROVIDER_MAIN_MENU}"


def provider_post_registration_menu_message() -> str:
    """Genera el menú posterior al registro de proveedor."""
    return f"{PROVIDER_POST_REGISTRATION_MENU}"


def provider_services_menu_message(servicios: List[str], max_servicios: int) -> str:
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
