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

CONSENT_FOOTER = "*Responde con el número de tu opción:*"

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
    f"{CONSENT_FOOTER}\n"
    "\n"
    "1) Registro\n"
    "2) Salir\n"
)


def consent_options_block() -> str:
    return "\n".join(
        [
            "1) Si, autorizo el uso de mis datos",
            "2) No autorizo el uso de mis datos",
        ]
    )


def consent_prompt_messages() -> List[str]:
    return [
        f"{CONSENT_PROMPT}\n\n{CONSENT_SCOPE_BLOCK}",
        f"{CONSENT_FOOTER}\n\n{consent_options_block()}",
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
    return f"{PROVIDER_MAIN_MENU}"


PROVIDER_POST_REGISTRATION_MENU = (
    "**Menú de Proveedor**\n"
    "\n"
    f"{CONSENT_FOOTER}\n"
    "\n"
    "1) Gestionar servicios\n"
    "2) Actualizar selfie\n"
    "3) Actualizar redes sociales (Instagram/Facebook)\n"
    "4) Salir\n"
)


def provider_post_registration_menu_message() -> str:
    return f"{PROVIDER_POST_REGISTRATION_MENU}"


def provider_under_review_message() -> str:
    return (
        "**Listo. Estamos revisando tu perfil; si falta algo, te escribimos.**"
    )


def provider_verified_message() -> str:
    return (
        "✅ Tu perfil ha sido verificado y autorizado para unirte a la comunidad TinkuBot. "
        "Ya puedes gestionar tu perfil y atender solicitudes de clientes."
    )


def provider_approved_notification(name: str = "") -> str:
    parts = [part for part in str(name).split() if part] if name else []
    short_name = " ".join(parts[:2])
    saludo = f"Hola {short_name}," if short_name else "Hola,"
    return (
        f"{saludo} ✅ tu perfil está aprobado. Bienvenido/a a TinkuBot; "
        "permanece pendiente de las próximas solicitudes."
    )


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
        f"{CONSENT_FOOTER} {limite_texto}".strip(),
        "",
        "1) Agregar servicio",
        "2) Eliminar servicio",
        "3) Volver al menú principal",
    ]

    cuerpo = encabezado + listado + opciones
    return "\n".join(part for part in cuerpo if part is not None)


# === MENSAJES DE EXPIRACIÓN DE SESIÓN ===


def session_timeout_warning_message(remaining_minutes: int, state: str = "") -> str:
    """Mensaje de advertencia cuando la sesión está por expirar."""
    return (
        f"⏰ *Tu sesión está por expirar*\n\n"
        f"Tienes {remaining_minutes} minutos para completar el paso actual. "
        f"Si no respondes a tiempo, tendrás que empezar de nuevo."
    )


def session_expired_message() -> str:
    """Mensaje cuando la sesión ha expirado."""
    return (
        "⌛ *Tu sesión ha expirado*\n\n"
        "Tardaste mucho tiempo en responder y tu sesión ha cerrado por seguridad. "
        "Para continuar, necesitas empezar desde el principio.\n\n"
        "Envía *hola* o *inicio* para comenzar nuevamente."
    )


def session_state_expired_mapping(state: str) -> str:
    """Retorna un mensaje específ según el estado que expiró."""
    messages = {
        "awaiting_consent": "El tiempo para dar tu consentimiento ha expirado.",
        "awaiting_city": "El tiempo para ingresar tu ciudad ha expirado.",
        "awaiting_name": "El tiempo para ingresar tu nombre ha expirado.",
        "awaiting_profession": "El tiempo para ingresar tu profesión ha expirado.",
        "awaiting_specialty": "El tiempo para ingresar tus servicios ha expirado.",
        "awaiting_experience": "El tiempo para ingresar tu experiencia ha expirado.",
        "awaiting_email": "El tiempo para ingresar tu correo ha expirado.",
        "awaiting_social_media": "El tiempo para ingresar tus redes sociales ha expirado.",
        "awaiting_dni_front_photo": "El tiempo para subir la foto del DNI frontal ha expirado.",
        "awaiting_dni_back_photo": "El tiempo para subir la foto del DNI reverso ha expirado.",
        "awaiting_face_photo": "El tiempo para subir tu selfie ha expirado.",
        "confirm": "El tiempo para confirmar tu registro ha expirado.",
        "pending_verification": "El tiempo de verificación ha expirado.",
    }
    return messages.get(state, "El tiempo para completar este paso ha expirado.")
