"""Mensajes relacionados con el consentimiento de datos del proveedor."""

from templates.interfaz.componentes import pie_instrucciones_respuesta_numerica

# ==================== CONSTANTES ====================

PROMPT_CONSENTIMIENTO = (
    "Hola, soy TinkuBot y estoy aqui para ayudarte a crear tu perfil de proveedor.\n\n"
    "Antes de continuar necesito tu autorizacion para guardar tus datos y compartirlos "
    "con clientes que busquen tus servicios a traves de nuestra plataforma."
)

BLOQUE_ALCANCE_CONSENTIMIENTO = (
    "Datos que almacenaremos:\n"
    "- Nombre completo\n"
    "- Telefono y ciudad\n"
    "- Profesion y años de experiencia\n"
    "- Opcionalmente, tu correo y redes sociales\n\n"
    "Usaremos esta informacion unicamente para conectar tus servicios con clientes "
    "interesados. Puedes solicitar la eliminacion de tus datos en cualquier momento."
)

OPCIONES_CONSENTIMIENTO = [
    "Si, autorizo el uso de mis datos",
    "No autorizo el uso de mis datos",
]

# ==================== FUNCIONES ====================


def bloque_opciones_consentimiento() -> str:
    """Genera el bloque de opciones numeradas para consentimiento."""
    return "\n".join(
        [
            "1) Si, autorizo el uso de mis datos",
            "2) No autorizo el uso de mis datos",
        ]
    )


def mensajes_prompt_consentimiento() -> list:
    """Genera los mensajes completos para solicitud de consentimiento."""
    return [
        f"{PROMPT_CONSENTIMIENTO}\n\n{BLOQUE_ALCANCE_CONSENTIMIENTO}",
        f"{pie_instrucciones_respuesta_numerica}\n\n{bloque_opciones_consentimiento()}",
    ]


def mensaje_consentimiento_aceptado() -> str:
    """Mensaje de confirmación cuando el proveedor acepta el consentimiento."""
    return (
        "Gracias. Registre tu consentimiento. Continuemos con la creacion de tu perfil."
    )


def mensaje_consentimiento_rechazado() -> str:
    """Mensaje cuando el proveedor rechaza el consentimiento."""
    return (
        "Entendido. Sin tu consentimiento no puedo registrar tu perfil ni compartir tus datos.\n\n"
        'Si cambias de opinión más adelante, escribe "registro" y continuamos desde aquí. '
        "Gracias por tu tiempo."
    )
