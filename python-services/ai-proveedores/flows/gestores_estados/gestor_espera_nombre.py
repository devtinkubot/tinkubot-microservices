"""Manejador del estado awaiting_name."""

from typing import Any, Dict, Optional

from services.servicios_proveedor.utilidades import limpiar_espacios


def manejar_espera_nombre(
    flujo: Dict[str, Any], texto_mensaje: Optional[str]
) -> Dict[str, Any]:
    """Procesa la entrada del usuario para el campo nombre.

    Args:
        flujo: Diccionario del flujo conversacional.
        texto_mensaje: Mensaje del usuario con el nombre.

    Returns:
        Respuesta con éxito y siguiente pregunta, o error de validación.
    """
    nombre = limpiar_espacios(texto_mensaje)
    if len(nombre) < 2:
        return {
            "success": True,
            "messages": [{"response": "*Por favor, enviame tu nombre completo.*"}],
        }

    flujo["name"] = nombre
    # Fase 4: Eliminada referencia a awaiting_profession - salto directo a awaiting_specialty
    flujo["state"] = "awaiting_specialty"
    return {
        "success": True,
        "messages": [
            {
                "response": (
                    "*¿Qué servicios ofreces?* Sepáralos con comas "
                    "(ej: instalación eléctrica, mantenimiento industrial, consultoría)."
                )
            }
        ],
    }
