"""Mensajes relacionados con menús de proveedores."""

from typing import List, Optional
from .componentes import pie_instrucciones_respuesta_numerica

# ==================== MENSAJES ====================

MENU_PRINCIPAL_PROVEEDOR = (
    "*Menú de Proveedores*\n"
    "\n"
    f"{pie_instrucciones_respuesta_numerica}\n"
    "\n"
    "*1.* Registro\n"
    "*2.* Salir\n"
)

MENU_POST_REGISTRO_PROVEEDOR = (
    "*Menú de Proveedores*\n"
    "\n"
    "*1.* Gestionar servicios\n"
    "*2.* Actualizar selfie\n"
    "*3.* Actualizar redes sociales\n"
    "*4.* Eliminar mi registro\n"
    "*5.* Salir\n"
    "\n"
    "*Responde con el número de opción para ver detalles.*\n"
)

MENU_POST_REGISTRO_PROVEEDOR_LIMITADO = (
    "*Menú de Proveedores*\n"
    "\n"
    "Tu perfil sigue en revisión. Puedes actualizar tu información mientras termina la validación.\n"
    "\n"
    "*1.* Gestionar servicios\n"
    "*2.* Actualizar selfie\n"
    "*3.* Actualizar redes sociales\n"
    "*4.* Actualizar cédula\n"
    "*5.* Salir\n"
    "\n"
    "*Responde con el número de opción para ver detalles.*\n"
)

# ==================== FUNCIONES ====================


def mensaje_menu_principal_proveedor() -> str:
    """Genera el menú principal de proveedores."""
    return f"{MENU_PRINCIPAL_PROVEEDOR}"


def mensaje_menu_post_registro_proveedor(menu_limitado: bool = False) -> str:
    """Genera el menú posterior al registro de proveedor."""
    if menu_limitado:
        return f"{MENU_POST_REGISTRO_PROVEEDOR_LIMITADO}"
    return f"{MENU_POST_REGISTRO_PROVEEDOR}"


def mensaje_menu_servicios_proveedor(
    servicios: List[str],
    max_servicios: int,
    servicios_pendientes_genericos: Optional[List[str]] = None,
) -> str:
    """Genera el selector principal de gestión de servicios."""
    pendientes = [
        servicio.strip()
        for servicio in (servicios_pendientes_genericos or [])
        if str(servicio or "").strip()
    ]
    activos_count = len(servicios or [])
    pendientes_count = len(pendientes)

    cuerpo = [
        "*Gestión de Servicios*",
        "",
        f"Activos: {activos_count}",
        f"Pendientes por precisar: {pendientes_count}",
        "",
        f"*{pie_instrucciones_respuesta_numerica}*",
        "",
        "*1.* Gestionar servicios activos",
        "*2.* Gestionar servicios pendientes",
        "*3.* Volver al menú principal",
    ]
    if max_servicios:
        cuerpo.insert(5, f"(*Nota:* Puedes tener hasta {max_servicios} servicios activos).")
        cuerpo.insert(6, "")
    return "\n".join(cuerpo)


def mensaje_menu_servicios_activos(
    servicios: List[str],
    max_servicios: int,
) -> str:
    """Genera el menú de gestión de servicios activos."""
    encabezado = ["*Gestión de Servicios Activos*", ""]

    if servicios:
        listado = ["*Servicios activos:*", ""]
        listado.extend(
            [f"{idx + 1}. {servicio}" for idx, servicio in enumerate(servicios)]
        )
        listado.append("")
    else:
        listado = ["Todavía no registras servicios activos.", ""]

    limite_texto = (
        f"(*Nota:* Puedes tener hasta {max_servicios} servicios activos)."
        if max_servicios
        else ""
    )

    opciones = [
        f"*{pie_instrucciones_respuesta_numerica}*",
        limite_texto,
        "",
        "*1.* Agregar servicio",
        "*2.* Eliminar servicio",
        "*3.* Volver a gestión de servicios",
    ]

    cuerpo = encabezado + listado + opciones
    return "\n".join(part for part in cuerpo if part is not None)


def mensaje_menu_servicios_pendientes(
    servicios_pendientes_genericos: Optional[List[str]] = None,
) -> str:
    """Genera el menú de gestión de servicios pendientes."""
    pendientes = [
        servicio.strip()
        for servicio in (servicios_pendientes_genericos or [])
        if str(servicio or "").strip()
    ]
    encabezado = [
        "*Gestión de Servicios Pendientes*",
        "",
        "⚠️ Estos servicios no participan en búsquedas hasta que los detalles.",
        "",
    ]
    if pendientes:
        listado = ["*Servicios pendientes por precisar:*", ""]
        listado.extend(
            [
                f"{idx + 1}. {servicio} *(genérico)*"
                for idx, servicio in enumerate(pendientes)
            ]
        )
        listado.append("")
    else:
        listado = ["No tienes servicios pendientes por precisar.", ""]

    opciones = [
        f"*{pie_instrucciones_respuesta_numerica}*",
        "",
        "*1.* Precisar un servicio pendiente",
        "*2.* Volver a gestión de servicios",
    ]
    return "\n".join(encabezado + listado + opciones)
