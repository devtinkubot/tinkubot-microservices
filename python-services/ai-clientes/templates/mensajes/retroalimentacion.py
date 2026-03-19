"""Mensajes relacionados con retroalimentación y satisfacción del cliente."""


def mensaje_solicitud_retroalimentacion(nombre_proveedor: str) -> str:
    """Mensaje de texto simple (fallback) para retroalimentación.

    Args:
        nombre_proveedor: Nombre del proveedor con el que se conectó.

    Returns:
        Mensaje con opciones de rating.
    """
    return (
        f"*¿Cómo te fue con {nombre_proveedor}?*\n\n"
        "*Calificar a nuestros expertos nos ayuda a mejorar el servicio que te entregamos. "
        "Tu opinión hace la diferencia y nos toma muy poco tiempo.*\n\n"
        "*Responde con el número de tu opción:*\n\n"
        "*1.* ⭐ Excelente\n"
        "*2.* ✓ Bien\n"
        "*3.* 😐 Regular\n"
        "*4.* ✗ No lo contraté\n"
        "*5.* ❌ Mal servicio\n"
        "*6.* Prefiero no responder\n\n"
        "Por favor elige una opción de la lista."
    )


def ui_retroalimentacion_contratacion(nombre_proveedor: str) -> dict:
    """UI config para lista interactiva de retroalimentación.

    Args:
        nombre_proveedor: Nombre del proveedor con el que se conectó.

    Returns:
        Configuración de UI para lista interactiva con rating.
    """
    return {
        "type": "list",
        "list_button_text": "Calificar servicio",
        "list_section_title": "Tu experiencia",
        "options": [
            {"id": "excellent", "title": "⭐ Excelente", "description": "Superó mis expectativas"},
            {"id": "good", "title": "✓ Bien", "description": "Me sirvió"},
            {"id": "regular", "title": "😐 Regular", "description": "Podría mejorar"},
            {"id": "not_hired", "title": "✗ No lo contraté", "description": "Decidí no contratar"},
            {"id": "bad", "title": "❌ Mal servicio", "description": "No lo recomiendo"},
            {
                "id": "prefer_not_to_answer",
                "title": "Prefiero no responder",
                "description": "Cierro esta solicitud sin calificar",
            },
        ],
    }


def mensaje_gracias_feedback() -> str:
    """Mensaje de agradecimiento tras recibir feedback del cliente."""
    return "*¡Gracias por tu respuesta!* Tu feedback nos ayuda a mejorar."


def mensaje_opcion_invalida_feedback() -> str:
    """Mensaje cuando la respuesta de feedback no es válida."""
    return "Por favor elige una opción de la lista o responde con un número del 1 al 6."
