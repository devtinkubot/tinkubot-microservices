"""Mensajes relacionados con el consentimiento de datos del cliente."""

from templates.comunes import pie_instrucciones_respuesta_numerica

# ==================== MENSAJES ====================

mensaje_consentimiento_datos = """*¡Hola! Soy TinkuBot 🔧*

Para buscar profesionales cercanos.

📋 Usaré:
* Tu teléfono
* Ciudad
* Necesidad/Problema a resolver

🔒 Solo para mostrarte resultados disponibles

¿Aceptas que TinkuBot use tus datos?"""

opciones_consentimiento_textos = ["Acepto", "No acepto"]


# ==================== FUNCIONES ====================

def menu_opciones_consentimiento() -> str:
    """Genera el bloque de opciones numeradas para consentimiento."""
    return "\n".join(
        [
            "*1.* Acepto",
            "*2.* No acepto",
        ]
    )


def mensajes_flujo_consentimiento() -> list[str]:
    """Genera los mensajes completos para solicitud de consentimiento."""
    return [
        f"{mensaje_consentimiento_datos}",
        f"*{pie_instrucciones_respuesta_numerica}*\n\n{menu_opciones_consentimiento()}",
    ]


def mensaje_rechazo_consentimiento() -> str:
    """Mensaje cuando el usuario rechaza que TinkuBot use sus datos.

    Returns:
        Mensaje explicativo con opción de reconsiderar.
    """
    return """Entendido. Sin tu consentimiento no puedo buscar profesionales para ti.

Si cambias de opinión, simplemente escribe "hola" y podremos empezar de nuevo.

📞 ¿Necesitas ayuda directamente? Llámanos al [número de atención al cliente]"""
