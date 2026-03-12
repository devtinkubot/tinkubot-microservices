"""Mensajes relacionados con menús de proveedores."""

from typing import Any, Dict, List

from .componentes import pie_instrucciones_respuesta_numerica

# ==================== MENSAJES ====================

MENU_HEADER_TEXT = "TinkuBot Proveedores"

MENU_ID_INFO_PERSONAL = "provider_menu_info_personal"
MENU_ID_INFO_PROFESIONAL = "provider_menu_info_profesional"
MENU_ID_ELIMINAR_REGISTRO = "provider_menu_eliminar_registro"
MENU_ID_SALIR = "provider_menu_salir"

SUBMENU_ID_PERSONAL_NOMBRE = "provider_submenu_personal_nombre"
SUBMENU_ID_PERSONAL_UBICACION = "provider_submenu_personal_ubicacion"
SUBMENU_ID_PERSONAL_DOCUMENTOS = "provider_submenu_personal_documentos"
SUBMENU_ID_PERSONAL_FOTO = "provider_submenu_personal_foto"

SUBMENU_ID_PROF_SERVICIOS = "provider_submenu_profesional_servicios"
SUBMENU_ID_PROF_CERTIFICADOS = "provider_submenu_profesional_certificados"
SUBMENU_ID_PROF_REDES = "provider_submenu_profesional_redes"

MENU_PRINCIPAL_PROVEEDOR = (
    "*Menú de Proveedores*\n"
    "\n"
    f"{pie_instrucciones_respuesta_numerica}\n"
    "\n"
    "*1.* Registro\n"
    "*2.* Salir\n"
)

MENU_POST_REGISTRO_PROVEEDOR = (
    "*Menú del Proveedor*\n"
    "\n"
    "*1.* Información personal\n"
    "*2.* Información profesional\n"
    "*3.* Eliminar mi registro\n"
    "*4.* Salir\n"
    "\n"
    "*Elige la opción de interés.*\n"
)

MENU_POST_REGISTRO_PROVEEDOR_LIMITADO = (
    "*Menú de Proveedores*\n"
    "\n"
    "Tu perfil sigue en revisión. Puedes actualizar tu información "
    "mientras termina la validación.\n"
    "\n"
    "*1.* Gestionar servicios\n"
    "*2.* Actualizar foto de perfil\n"
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


def payload_menu_post_registro_proveedor() -> Dict[str, Any]:
    """Genera el menú principal operativo como lista interactiva."""
    return {
        "response": (
            f"*{MENU_HEADER_TEXT}*\n\n"
            "Elige la opción de interés."
        ),
        "ui": {
            "type": "list",
            "id": "provider_main_menu_v1",
            "list_button_text": "Ver menú",
            "list_section_title": "Menú del Proveedor",
            "options": [
                {
                    "id": MENU_ID_INFO_PERSONAL,
                    "title": "Información personal",
                    "description": "Nombre, ubicación, documentos y foto de perfil",
                },
                {
                    "id": MENU_ID_INFO_PROFESIONAL,
                    "title": "Información profesional",
                    "description": "Servicios, certificados y redes sociales",
                },
                {
                    "id": MENU_ID_ELIMINAR_REGISTRO,
                    "title": "Eliminar mi registro",
                    "description": "Eliminar permanentemente tu perfil",
                },
                {
                    "id": MENU_ID_SALIR,
                    "title": "Salir",
                    "description": "Cerrar el menú actual",
                },
            ],
        },
    }


def payload_submenu_informacion_personal() -> Dict[str, Any]:
    """Genera el submenú de información personal."""
    return {
        "response": (
            f"*{MENU_HEADER_TEXT}*\n\n"
            "Información personal. Elige lo que deseas gestionar."
        ),
        "ui": {
            "type": "list",
            "id": "provider_personal_info_menu_v1",
            "list_button_text": "Ver opciones",
            "list_section_title": "Información personal",
            "options": [
                {
                    "id": SUBMENU_ID_PERSONAL_NOMBRE,
                    "title": "Nombre",
                    "description": "Actualizar tu nombre visible",
                },
                {
                    "id": SUBMENU_ID_PERSONAL_UBICACION,
                    "title": "Ubicación",
                    "description": "Cambiar ciudad o compartir ubicación",
                },
                {
                    "id": SUBMENU_ID_PERSONAL_DOCUMENTOS,
                    "title": "Documentos de identidad",
                    "description": "Actualizar cédula frontal y posterior",
                },
                {
                    "id": SUBMENU_ID_PERSONAL_FOTO,
                    "title": "Foto de perfil",
                    "description": "Actualizar tu foto de perfil",
                },
            ],
        },
    }


def payload_submenu_informacion_profesional() -> Dict[str, Any]:
    """Genera el submenú de información profesional."""
    return {
        "response": (
            f"*{MENU_HEADER_TEXT}*\n\n"
            "Información profesional. Elige lo que deseas gestionar."
        ),
        "ui": {
            "type": "list",
            "id": "provider_professional_info_menu_v1",
            "list_button_text": "Ver opciones",
            "list_section_title": "Información profesional",
            "options": [
                {
                    "id": SUBMENU_ID_PROF_SERVICIOS,
                    "title": "Servicios",
                    "description": "Agregar o eliminar servicios",
                },
                {
                    "id": SUBMENU_ID_PROF_CERTIFICADOS,
                    "title": "Certificados",
                    "description": "Subir o reemplazar tu certificado activo",
                },
                {
                    "id": SUBMENU_ID_PROF_REDES,
                    "title": "Redes sociales",
                    "description": "Actualizar tu red social profesional",
                },
            ],
        },
    }


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
