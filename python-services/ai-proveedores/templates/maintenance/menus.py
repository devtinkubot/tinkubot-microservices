"""Mensajes relacionados con menús de proveedores."""

from typing import Any, Dict, List, Optional

from templates.shared import mensaje_elige_opcion_interes

MENU_ID_INFO_PERSONAL = "provider_menu_info_personal"
MENU_ID_INFO_PROFESIONAL = "provider_menu_info_profesional"
MENU_ID_ELIMINAR_REGISTRO = "provider_menu_eliminar_registro"
MENU_ID_SALIR = "provider_menu_salir"

SUBMENU_ID_PERSONAL_NOMBRE = "provider_submenu_personal_nombre"
SUBMENU_ID_PERSONAL_UBICACION = "provider_submenu_personal_ubicacion"
SUBMENU_ID_PERSONAL_DOCUMENTOS = "provider_submenu_personal_documentos"
SUBMENU_ID_PERSONAL_FOTO = "provider_submenu_personal_foto"
SUBMENU_ID_PERSONAL_DNI_FRONTAL = "provider_submenu_personal_dni_frontal"
SUBMENU_ID_PERSONAL_DNI_REVERSO = "provider_submenu_personal_dni_reverso"
SUBMENU_ID_PERSONAL_REGRESAR = "provider_submenu_personal_regresar"

SUBMENU_ID_PROF_SERVICIOS = "provider_submenu_profesional_servicios"
SUBMENU_ID_PROF_EXPERIENCIA = "provider_submenu_profesional_experiencia"
SUBMENU_ID_PROF_CERTIFICADOS = "provider_submenu_profesional_certificados"
SUBMENU_ID_PROF_REDES = "provider_submenu_profesional_redes"
SUBMENU_ID_PROF_REGRESAR = "provider_submenu_profesional_regresar"
SOCIAL_NETWORK_FACEBOOK_ID = "provider_social_facebook"
SOCIAL_NETWORK_INSTAGRAM_ID = "provider_social_instagram"
SOCIAL_NETWORK_BACK_ID = "provider_social_back"

DETAIL_ACTION_NAME_CHANGE = "provider_detail_name_change"
DETAIL_ACTION_CITY_CHANGE = "provider_detail_city_change"
DETAIL_ACTION_PHOTO_CHANGE = "provider_detail_photo_change"
DETAIL_ACTION_DNI_FRONT_CHANGE = "provider_detail_dni_front_change"
DETAIL_ACTION_DNI_BACK_CHANGE = "provider_detail_dni_back_change"
DETAIL_ACTION_EXPERIENCE_CHANGE = "provider_detail_experience_change"
DETAIL_ACTION_SOCIAL_CHANGE = "provider_detail_social_change"
DETAIL_ACTION_SERVICES_ADD = "provider_detail_services_add"
DETAIL_ACTION_SERVICES_REMOVE = "provider_detail_services_remove"
DETAIL_ACTION_SERVICE_CHANGE = "provider_detail_service_change"
DETAIL_ACTION_SERVICE_DELETE = "provider_detail_service_delete"
DETAIL_ACTION_CERTIFICATES_ADD = "provider_detail_certificates_add"
DETAIL_ACTION_CERTIFICATES_DELETE = "provider_detail_certificates_delete"
DETAIL_ACTION_BACK = "provider_detail_back"

SERVICE_SLOT_PREFIX = "provider_service_slot:"
SERVICE_BACK_ID = "provider_service_back"
SERVICE_DELETE_PREFIX = "provider_service_delete:"
SERVICE_DELETE_BACK_ID = "provider_service_delete_back"
CERTIFICATE_SELECT_PREFIX = "provider_certificate_select:"
CERTIFICATE_SLOT_PREFIX = "provider_certificate_slot:"
CERTIFICATE_ADD_ID = "provider_certificate_add"
SERVICE_EXAMPLE_BACK_ID = "provider_service_example_back"
CERTIFICATE_BACK_ID = "provider_certificate_back"
SERVICE_EXAMPLE_LIST_ID = "provider_service_examples_v1"
SERVICE_EXAMPLE_PREFIX = "provider_service_example:"
SERVICE_EXAMPLE_MECHANICS_ID = "provider_service_example_mechanics"
SERVICE_EXAMPLE_LEGAL_ID = "provider_service_example_legal"
SERVICE_EXAMPLE_ADMIN_ID = "provider_service_example_admin"
LIST_OPTION_DESCRIPTION_MAX = 72
LIST_OPTION_TITLE_MAX = 24

MENU_PRINCIPAL_PROVEEDOR = (
    "*Menú de Proveedores*\n" "\n" "Elige la opción de interés.\n"
)

MENU_POST_REGISTRO_PROVEEDOR = (
    "*Menú del Proveedor*\n" "\n" "Elige la opción de interés.\n"
)

# ==================== FUNCIONES ====================


def mensaje_menu_principal_proveedor() -> str:
    """Genera el menú principal de proveedores."""
    return f"{MENU_PRINCIPAL_PROVEEDOR}"


def mensaje_menu_post_registro_proveedor() -> str:
    """Genera el menú posterior al registro de proveedor."""
    return f"{MENU_POST_REGISTRO_PROVEEDOR}"


def payload_menu_post_registro_proveedor() -> Dict[str, Any]:
    """Genera el menú principal operativo como lista interactiva."""
    return {
        "response": mensaje_elige_opcion_interes(),
        "ui": {
            "type": "list",
            "id": "provider_main_menu_v1",
            "header_type": "text",
            "header_text": "Menu - Principal",
            "list_button_text": "Ver menú",
            "list_section_title": "Menú del Proveedor",
            "options": [
                {
                    "id": MENU_ID_INFO_PERSONAL,
                    "title": "Información personal",
                    "description": "Ubicación y foto de perfil",
                },
                {
                    "id": MENU_ID_INFO_PROFESIONAL,
                    "title": "Información profesional",
                    "description": (
                        "Experiencia, servicios, certificaciones y redes sociales"
                    ),
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
        "response": "Información personal. Elige lo que deseas gestionar.",
        "ui": {
            "type": "list",
            "id": "provider_personal_info_menu_v1",
            "header_type": "text",
            "header_text": "Menu - Informacion Personal",
            "list_button_text": "Ver opciones",
            "list_section_title": "Información personal",
            "options": [
                {
                    "id": SUBMENU_ID_PERSONAL_UBICACION,
                    "title": "Ubicación",
                    "description": "Cambiar ciudad o compartir ubicación",
                },
                {
                    "id": SUBMENU_ID_PERSONAL_FOTO,
                    "title": "Foto de perfil",
                    "description": "Ver o actualizar tu foto de perfil",
                },
                {
                    "id": SUBMENU_ID_PERSONAL_REGRESAR,
                    "title": "Regresar",
                    "description": "Volver al menú principal",
                },
            ],
        },
    }


def payload_submenu_informacion_profesional() -> Dict[str, Any]:
    """Genera el submenú de información profesional."""
    return {
        "response": "Información profesional. Elige lo que deseas gestionar.",
        "ui": {
            "type": "list",
            "id": "provider_professional_info_menu_v1",
            "header_type": "text",
            "header_text": "Menu - Informacion Profesional",
            "list_button_text": "Ver opciones",
            "list_section_title": "Información profesional",
            "options": [
                {
                    "id": SUBMENU_ID_PROF_EXPERIENCIA,
                    "title": "Experiencia general",
                    "description": "Ver o actualizar tus años de experiencia",
                },
                {
                    "id": SUBMENU_ID_PROF_SERVICIOS,
                    "title": "Servicios",
                    "description": "Ver, agregar o eliminar servicios",
                },
                {
                    "id": SUBMENU_ID_PROF_CERTIFICADOS,
                    "title": "Certificados",
                    "description": "Ver, agregar o eliminar certificados",
                },
                {
                    "id": SUBMENU_ID_PROF_REDES,
                    "title": "Redes sociales",
                    "description": "Ver o actualizar tu red social profesional",
                },
                {
                    "id": SUBMENU_ID_PROF_REGRESAR,
                    "title": "Regresar",
                    "description": "Volver al menú principal",
                },
            ],
        },
    }


def _formatear_header_ejemplos_servicios(
    indice: Optional[int] = None,
    maximo: Optional[int] = None,
) -> str:
    if indice is not None and maximo is not None:
        return f"Agregar Servicio {indice} de {maximo}"
    return "Ejemplos reales"


def payload_ejemplos_servicios_personalizados(
    ejemplos: Optional[List[Dict[str, str]]] = None,
    indice: Optional[int] = None,
    maximo: Optional[int] = None,
    include_back_option: bool = True,
) -> Dict[str, Any]:
    """Genera una lista de ejemplos de servicios con fallback fijo."""
    ejemplos_base = ejemplos or [
        {
            "id": SERVICE_EXAMPLE_MECHANICS_ID,
            "title": "Gasfitería",
            "description": (
                "Instalación y mantenimiento de tuberías para casas o edificios"
            ),
        },
        {
            "id": SERVICE_EXAMPLE_LEGAL_ID,
            "title": "Legal",
            "description": (
                "Asesoría legal en divorcios, pensiones y trámites de familia"
            ),
        },
        {
            "id": SERVICE_EXAMPLE_ADMIN_ID,
            "title": "Administrativo",
            "description": "Facturación, cobranza y gestión documental para negocios",
        },
    ]
    return {
        "response": (
            "Toca un dominio para ver un servicio real que se agrega con frecuencia. "
            "Después puedes escribir el tuyo directamente."
        ),
        "ui": {
            "type": "list",
            "id": SERVICE_EXAMPLE_LIST_ID,
            "header_type": "text",
            "header_text": _formatear_header_ejemplos_servicios(
                indice=indice,
                maximo=maximo,
            ),
            "footer_text": "¿Necesitas ideas?. Toca Ver ejemplos.",
            "list_button_text": "Ver ejemplos",
            "list_section_title": "Dominios más frecuentes",
            "options": [
                {
                    "id": str(item.get("id") or "").strip(),
                    "title": _truncar_titulo_lista(
                        str(item.get("title") or "").strip()
                    ),
                    "description": _truncar_descripcion_lista(
                        str(item.get("description") or "").strip()
                    ),
                }
                for item in ejemplos_base
                if str(item.get("id") or "").strip()
                and str(item.get("title") or "").strip()
            ]
            + (
                [
                    {
                        "id": SERVICE_EXAMPLE_BACK_ID,
                        "title": "Regresar",
                        "description": "Volver al menú anterior",
                    }
                ]
                if include_back_option
                else []
            ),
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
        cuerpo.extend([f"• {servicio}" for servicio in servicios])
        cuerpo.append("")
    else:
        cuerpo.extend(["Todavía no registras servicios.", ""])

    cuerpo.extend(
        [
            (
                f"(*Nota:* Puedes tener hasta {max_servicios} servicios registrados)."
                if max_servicios
                else ""
            ),
        ]
    )
    return "\n".join(cuerpo)


def _payload_botones_detalle(
    *,
    body: str,
    options: List[Dict[str, str]],
    header_text: str = "",
    header_media_url: str = "",
) -> Dict[str, Any]:
    ui: Dict[str, Any] = {
        "type": "buttons",
        "id": "provider_detail_actions_v1",
        "options": options,
    }
    media = str(header_media_url or "").strip()
    if media:
        ui["header_type"] = "image"
        ui["header_media_url"] = media
    if header_text:
        if not media:
            ui["header_type"] = "text"
        ui["header_text"] = header_text
    return {"response": body, "ui": ui}


def _truncar_descripcion_lista(
    valor: str, limite: int = LIST_OPTION_DESCRIPTION_MAX
) -> str:
    texto = " ".join(str(valor or "").strip().split())
    if len(texto) <= limite:
        return texto
    return texto[: max(limite - 1, 0)].rstrip() + "…"


def _truncar_titulo_lista(valor: str, limite: int = LIST_OPTION_TITLE_MAX) -> str:
    texto = " ".join(str(valor or "").strip().split())
    if len(texto) <= limite:
        return texto
    return texto[: max(limite - 3, 0)].rstrip() + "..."


def payload_detalle_nombre(
    nombre: str, *, permitir_cambio: bool = True
) -> Dict[str, Any]:
    nombre_visible = str(nombre or "").strip() or "No registrado"
    options = [{"id": DETAIL_ACTION_BACK, "title": "Regresar"}]
    if permitir_cambio:
        options.insert(0, {"id": DETAIL_ACTION_NAME_CHANGE, "title": "Cambiar"})
    return _payload_botones_detalle(
        header_text="Información personal",
        body=f"*Nombre actual*\n{nombre_visible}",
        options=options,
    )


def payload_detalle_ubicacion(ciudad: str) -> Dict[str, Any]:
    ciudad_visible = str(ciudad or "").strip() or "No registrada"
    return _payload_botones_detalle(
        header_text="Información personal",
        body=f"*Ubicación actual*\n{ciudad_visible}",
        options=[
            {"id": DETAIL_ACTION_CITY_CHANGE, "title": "Cambiar"},
            {"id": DETAIL_ACTION_BACK, "title": "Regresar"},
        ],
    )


def payload_detalle_experiencia(experiencia: Any) -> Dict[str, Any]:
    if isinstance(experiencia, str) and experiencia.strip():
        experiencia_visible = experiencia.strip()
    elif isinstance(experiencia, int) and experiencia >= 0:
        experiencia_visible = f"{experiencia} año{'s' if experiencia != 1 else ''}"
    else:
        experiencia_visible = "No registrada"
    return _payload_botones_detalle(
        header_text="Experiencia general",
        body=f"*Años registrados*\n{experiencia_visible}",
        options=[
            {"id": DETAIL_ACTION_EXPERIENCE_CHANGE, "title": "Cambiar"},
            {"id": DETAIL_ACTION_BACK, "title": "Regresar"},
        ],
    )


def payload_detalle_foto(
    *,
    titulo: str,
    descripcion: str,
    media_url: str,
    change_id: Optional[str] = None,
) -> Dict[str, Any]:
    options = [{"id": DETAIL_ACTION_BACK, "title": "Regresar"}]
    if change_id:
        options.insert(0, {"id": change_id, "title": "Cambiar"})
    return _payload_botones_detalle(
        header_text=titulo,
        header_media_url=media_url,
        body=descripcion,
        options=options,
    )


def payload_detalle_red_social(url: str) -> Dict[str, Any]:
    url_visible = str(url or "").strip() or "No registrada"
    return _payload_botones_detalle(
        header_text="Redes sociales",
        body=f"*Red social actual*\n{url_visible}",
        options=[
            {"id": DETAIL_ACTION_SOCIAL_CHANGE, "title": "Cambiar"},
            {"id": DETAIL_ACTION_BACK, "title": "Regresar"},
        ],
    )


def payload_lista_redes_sociales(
    *,
    facebook_username: Optional[str],
    instagram_username: Optional[str],
) -> Dict[str, Any]:
    return {
        "response": "Redes sociales. Elige lo que deseas gestionar.",
        "ui": {
            "type": "list",
            "id": "provider_social_networks_v1",
            "header_type": "text",
            "header_text": "Menu - Redes Sociales",
            "list_button_text": "Ver redes",
            "list_section_title": "Redes sociales",
            "options": [
                {
                    "id": SOCIAL_NETWORK_FACEBOOK_ID,
                    "title": "Facebook",
                    "description": (
                        "Registrada" if facebook_username else "No registrada"
                    ),
                },
                {
                    "id": SOCIAL_NETWORK_INSTAGRAM_ID,
                    "title": "Instagram",
                    "description": (
                        "Registrada" if instagram_username else "No registrada"
                    ),
                },
                {
                    "id": SOCIAL_NETWORK_BACK_ID,
                    "title": "Regresar",
                    "description": "Volver a información profesional",
                },
            ],
        },
    }


def payload_detalle_red_social_canal(
    *,
    titulo: str,
    username: Optional[str],
    url: Optional[str],
) -> Dict[str, Any]:
    username_visible = str(username or "").strip() or "No registrado"
    url_visible = str(url or "").strip() or "No registrada"
    return _payload_botones_detalle(
        header_text=titulo,
        body=f"*Usuario actual*\n{username_visible}\n\n*URL actual*\n{url_visible}",
        options=[
            {"id": DETAIL_ACTION_SOCIAL_CHANGE, "title": "Cambiar"},
            {"id": DETAIL_ACTION_BACK, "title": "Regresar"},
        ],
    )


def payload_detalle_servicios(
    servicios: List[str], max_servicios: int
) -> Dict[str, Any]:
    maximo_slots_visibles = max(min(max_servicios, 9), 0)
    options = [
        {
            "id": f"{SERVICE_SLOT_PREFIX}{idx}",
            "title": f"Servicio {idx + 1}",
            "description": (
                _truncar_descripcion_lista(servicios[idx])
                if idx < min(len(servicios), maximo_slots_visibles)
                else "No registrado"
            ),
        }
        for idx in range(maximo_slots_visibles)
    ]
    options.append(
        {
            "id": SERVICE_BACK_ID,
            "title": "Regresar",
            "description": "Volver a información profesional",
        }
    )
    return {
        "response": "Servicios. Elige lo que deseas gestionar.",
        "ui": {
            "type": "list",
            "id": "provider_services_v2",
            "header_type": "text",
            "header_text": "Menu - Servicios",
            "list_button_text": "Ver servicios",
            "list_section_title": "Servicios",
            "options": options,
        },
    }


def payload_detalle_servicio_individual(
    *,
    indice: int,
    servicio: str,
    registrado: bool = True,
) -> Dict[str, Any]:
    options = [
        {"id": DETAIL_ACTION_SERVICE_CHANGE, "title": "Cambiar"},
    ]
    if registrado:
        options.append({"id": DETAIL_ACTION_SERVICE_DELETE, "title": "Eliminar"})
    options.append({"id": DETAIL_ACTION_BACK, "title": "Regresar"})
    return _payload_botones_detalle(
        header_text=f"Servicio {indice + 1}",
        body=f"*Servicio actual*\n{str(servicio or '').strip() or 'No registrado'}",
        options=options,
    )


def payload_lista_eliminar_servicios(servicios: List[str]) -> Dict[str, Any]:
    options = [
        {
            "id": f"{SERVICE_DELETE_PREFIX}{idx}",
            "title": f"Servicio {idx + 1}",
            "description": _truncar_descripcion_lista(servicio),
        }
        for idx, servicio in enumerate(servicios)
    ]
    options.append(
        {
            "id": SERVICE_DELETE_BACK_ID,
            "title": "Regresar",
            "description": "Volver a servicios registrados",
        }
    )
    return {
        "response": "Selecciona el servicio que deseas eliminar.",
        "ui": {
            "type": "list",
            "id": "provider_service_delete_list_v1",
            "header_type": "text",
            "header_text": "Menu - Eliminar Servicios",
            "list_button_text": "Ver servicios",
            "list_section_title": "Eliminar servicios",
            "options": options,
        },
    }


def payload_lista_certificados(
    certificados: List[Dict[str, Any]],
    *,
    max_certificados: int,
) -> Dict[str, Any]:
    options = [
        {
            "id": f"{CERTIFICATE_SLOT_PREFIX}{idx}",
            "title": f"Certificado {idx + 1}",
            "description": "Registrado" if idx < len(certificados) else "No registrado",
        }
        for idx in range(max_certificados)
    ]
    options.append(
        {
            "id": CERTIFICATE_BACK_ID,
            "title": "Regresar",
            "description": "Volver a información profesional",
        }
    )
    response = f"*Certificados registrados ({len(certificados)}/{max_certificados})*"
    return {
        "response": response,
        "ui": {
            "type": "list",
            "id": "provider_certificates_list_v1",
            "header_type": "text",
            "header_text": "Menu - Certificados",
            "list_button_text": "Ver certificados",
            "list_section_title": "Certificados",
            "options": options,
        },
    }


def payload_detalle_certificado(
    *,
    certificado: Dict[str, Any],
    total: int,
    max_certificados: int,
    media_url: Optional[str] = None,
    body: str = "Certificado seleccionado.",
) -> Dict[str, Any]:
    media_resuelta = (
        str(certificado.get("file_url") or "").strip()
        if media_url is None
        else str(media_url or "").strip()
    )
    return _payload_botones_detalle(
        header_text=f"Certificado ({total}/{max_certificados})",
        header_media_url=media_resuelta,
        body=body,
        options=[
            {"id": DETAIL_ACTION_CERTIFICATES_ADD, "title": "Cambiar"},
            {"id": DETAIL_ACTION_BACK, "title": "Regresar"},
        ],
    )
