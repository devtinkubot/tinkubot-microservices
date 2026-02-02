"""Mensajes relacionados con el consentimiento de datos del proveedor."""

from templates.interfaz.componentes import pie_instrucciones_respuesta_numerica

# ==================== CONSTANTES ====================

PROMPT_CONSENTIMIENTO = (
    "¡Hola! Soy TinkuBot 🔧\n\n"
    "Te ayudaré a crear tu perfil para recibir clientes."
)

BLOQUE_ALCANCE_CONSENTIMIENTO = (
    "📋 *Guardaré:*\n"
    "• Nombre, teléfono y ciudad\n"
    "• Servicios y experiencia\n"
    "• Opcional: correo y redes\n\n"
    "🔒 *Solo para conectar tu servicios con clientes interesados*\n\n"
    "*¿Autorizas el uso de tus datos?*"
)

OPCIONES_CONSENTIMIENTO = [
    "Acepto",
    "No acepto",
]

# ==================== FUNCIONES ====================


def bloque_opciones_consentimiento() -> str:
    """Genera el bloque de opciones numeradas para consentimiento."""
    return "\n".join(
        [
            "1) Acepto",
            "2) No acepto",
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
