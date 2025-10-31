"""Textos base reutilizables para el servicio de proveedores."""

from typing import List

CONSENT_PROMPT = (
    "Hola, soy TinkuBot y estoy aqui para ayudarte a crear tu perfil de proveedor.\n\n"
    "Antes de continuar necesito tu autorizacion para guardar tus datos y compartirlos "
    "con clientes que busquen tus servicios a traves de nuestra plataforma."
)

CONSENT_SCOPE_BLOCK = (
    "Datos que almacenaremos:\n"
    "- Nombre completo\n"
    "- Telefono y ciudad\n"
    "- Profesion y años de experiencia\n"
    "- Opcionalmente, tu correo y redes sociales\n\n"
    "Usaremos esta informacion unicamente para conectar tus servicios con clientes "
    "interesados. Puedes solicitar la eliminacion de tus datos en cualquier momento."
)

CONSENT_OPTIONS = [
    "Si, autorizo el uso de mis datos",
    "No autorizo el uso de mis datos",
]

CONSENT_FOOTER = "*Responde con el numero de tu opcion:*"

REGISTRATION_START_PROMPT = (
    "Perfecto. Empecemos. En que ciudad trabajas principalmente?"
)

CONSENT_DECLINED_MESSAGE = (
    "Entendido. Sin tu consentimiento no puedo registrar tu perfil ni compartir tus datos.\n\n"
    'Si cambias de opinión más adelante, escribe "registro" y continuamos desde aquí. '
    "Gracias por tu tiempo."
)

GUIDANCE_MESSAGE = (
    "Hola, soy TinkuBot Proveedores. Puedo ayudarte a crear o actualizar tu perfil.\n"
    "Selecciona una opción del menú para continuar o escribe 'registro' para iniciar de inmediato."
)

PROVIDER_MAIN_MENU = (
    "**Menú de Proveedores**\n"
    "\n"
    "-----------------------------\n"
    "\n"
    "1. Registro\n"
    "2. Salir\n"
    "\n"
    "-----------------------------"
)


def consent_options_block() -> str:
    lines = [
        "..................",
        "",
        "1 Si, autorizo el uso de mis datos",
        "2 No autorizo el uso de mis datos",
        "",
        "..................",
    ]
    return "\n".join(lines)


def consent_prompt_messages() -> List[str]:
    return [
        f"{CONSENT_PROMPT}\n\n{CONSENT_SCOPE_BLOCK}",
        f"{consent_options_block()}\n{CONSENT_FOOTER}",
    ]


def consent_acknowledged_message() -> str:
    return (
        "Gracias. Registre tu consentimiento. Continuemos con la creacion de tu perfil."
    )


def consent_declined_message() -> str:
    return CONSENT_DECLINED_MESSAGE


def provider_guidance_message() -> str:
    return GUIDANCE_MESSAGE


def provider_main_menu_message() -> str:
    return f"{PROVIDER_MAIN_MENU}\n\n{CONSENT_FOOTER}"


PROVIDER_POST_REGISTRATION_MENU = (
    "**Menú de Proveedor**\n"
    "\n"
    "-----------------------------\n"
    "\n"
    "1. Gestionar servicios\n"
    "2. Actualizar selfie\n"
    "3. Salir\n"
    "\n"
    "-----------------------------"
)


def provider_post_registration_menu_message() -> str:
    return f"{PROVIDER_POST_REGISTRATION_MENU}\n\n{CONSENT_FOOTER}"


def provider_services_menu_message(servicios: List[str], max_servicios: int) -> str:
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
        "",
        "1. Agregar servicio",
        "2. Eliminar servicio",
        "3. Volver al menú principal",
        "",
        f"*Responde con el número de tu opción.* {limite_texto}".strip(),
    ]

    cuerpo = encabezado + listado + opciones
    return "\n".join(part for part in cuerpo if part is not None)
