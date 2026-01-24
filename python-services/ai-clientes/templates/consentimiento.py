"""Mensajes relacionados con el consentimiento de datos del cliente."""

from templates.comunes import pie_instrucciones_respuesta_numerica

# ==================== MENSAJES ====================

mensaje_consentimiento_datos = """¡Hola! Soy TinkuBot, tu asistente virtual para encontrar servicios confiables de forma rápida y segura.

Para poder conectararte con proveedores de servicios, necesito tu consentimiento para compartir tus datos de contacto únicamente con los profesionales seleccionados.

📋 *Información que compartiremos:*
• Tu número de teléfono
• Ciudad donde necesitas el servicio
• Tipo de servicio que solicitas

🔒 *Tus datos están seguros y solo se usan para esta consulta.*

*¿Aceptas compartir tus datos con proveedores?*"""

opciones_consentimiento_textos = ["Acepto", "No acepto"]


# ==================== FUNCIONES ====================

def menu_opciones_consentimiento() -> str:
    """Genera el bloque de opciones numeradas para consentimiento."""
    return "\n".join(
        [
            "1) Acepto",
            "2) No acepto",
        ]
    )


def mensajes_flujo_consentimiento() -> list[str]:
    """Genera los mensajes completos para solicitud de consentimiento."""
    return [
        f"{mensaje_consentimiento_datos}",
        f"{pie_instrucciones_respuesta_numerica}\n\n{menu_opciones_consentimiento()}",
    ]
