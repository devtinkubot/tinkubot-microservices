"""Mensajes relacionados con menús de proveedores."""

from typing import List

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
    "Tu perfil sigue en revisión. Puedes actualizar tu información "
    "mientras termina la validación.\n"
    "\n"
    "*1.* Gestionar servicios\n"
    "*2.* Actualizar selfie\n"
    "*3.* Actualizar redes sociales\n"
    "*4.* Actualizar cédula\n"
    "*5.* Salir\n"
    "\n"
    "*Responde con el número de opción para ver detalles.*\n"
)

MENU_POST_REGISTRO_PROVEEDOR_BASICO = (
    "*Menú de Proveedores*\n"
    "\n"
    "Tu registro básico ya fue aprobado. El siguiente paso es completar tu perfil "
    "profesional.\n"
    "\n"
    "*1.* Completar perfil profesional\n"
    "\n"
    "*Responde con el número de opción para continuar.*\n"
)

# ==================== FUNCIONES ====================


def mensaje_menu_principal_proveedor() -> str:
    """Genera el menú principal de proveedores."""
    return f"{MENU_PRINCIPAL_PROVEEDOR}"


def mensaje_menu_post_registro_proveedor(
    menu_limitado: bool = False,
    approved_basic: bool = False,
) -> str:
    """Genera el menú posterior al registro de proveedor."""
    if approved_basic:
        return f"{MENU_POST_REGISTRO_PROVEEDOR_BASICO}"
    if menu_limitado:
        return f"{MENU_POST_REGISTRO_PROVEEDOR_LIMITADO}"
    return f"{MENU_POST_REGISTRO_PROVEEDOR}"


def mensaje_menu_servicios_proveedor(
    servicios: List[str],
    max_servicios: int,
) -> str:
    """Genera el menú único de gestión de servicios."""
    cuerpo = ["*Gestión de Servicios*", "", f"Registrados: {len(servicios or [])}", ""]
    if servicios:
        cuerpo.extend(["*Servicios registrados:*", ""])
        cuerpo.extend(
            [f"{idx + 1}. {servicio}" for idx, servicio in enumerate(servicios)]
        )
        cuerpo.append("")
    else:
        cuerpo.extend(["Todavía no registras servicios.", ""])

    cuerpo.extend(
        [
            f"*{pie_instrucciones_respuesta_numerica}*",
            (
                f"(*Nota:* Puedes tener hasta {max_servicios} servicios registrados)."
                if max_servicios
                else ""
            ),
            "",
            "*1.* Agregar servicio",
            "*2.* Eliminar servicio",
            "*3.* Volver al menú principal",
        ]
    )
    return "\n".join(cuerpo)
