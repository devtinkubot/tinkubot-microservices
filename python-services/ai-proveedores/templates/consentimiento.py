"""Mensajes relacionados con el consentimiento de datos del proveedor."""

from templates.comunes import pie_instrucciones_respuesta_numerica

# ==================== CONSTANTES ====================

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

# ==================== FUNCIONES ====================


def consent_options_block() -> str:
    """Genera el bloque de opciones numeradas para consentimiento."""
    return "\n".join(
        [
            "1) Si, autorizo el uso de mis datos",
            "2) No autorizo el uso de mis datos",
        ]
    )


def consent_prompt_messages() -> list:
    """Genera los mensajes completos para solicitud de consentimiento."""
    return [
        f"{CONSENT_PROMPT}\n\n{CONSENT_SCOPE_BLOCK}",
        f"{pie_instrucciones_respuesta_numerica}\n\n{consent_options_block()}",
    ]


def consent_acknowledged_message() -> str:
    """Mensaje de confirmación cuando el proveedor acepta el consentimiento."""
    return (
        "Gracias. Registre tu consentimiento. Continuemos con la creacion de tu perfil."
    )


def consent_declined_message() -> str:
    """Mensaje cuando el proveedor rechaza el consentimiento."""
    return (
        "Entendido. Sin tu consentimiento no puedo registrar tu perfil ni compartir tus datos.\n\n"
        'Si cambias de opinión más adelante, escribe "registro" y continuamos desde aquí. '
        "Gracias por tu tiempo."
    )
