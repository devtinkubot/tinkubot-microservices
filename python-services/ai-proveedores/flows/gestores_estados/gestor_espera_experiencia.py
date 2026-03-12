"""Manejador del estado awaiting_experience."""

from typing import Any, Dict, Optional

from services.servicios_proveedor.utilidades import extraer_anios_experiencia as parsear_anios_experiencia
from templates.registro import (
    construir_resumen_confirmacion_perfil_profesional,
    payload_confirmacion_resumen,
    payload_red_social_opcional,
)


def manejar_espera_experiencia(
    flujo: Dict[str, Any], texto_mensaje: Optional[str]
) -> Dict[str, Any]:
    """Procesa la entrada del usuario para el campo años de experiencia.

    Args:
        flujo: Diccionario del flujo conversacional.
        texto_mensaje: Mensaje del usuario con los años.

    Returns:
        Respuesta con éxito y siguiente pregunta, o error de validación.
    """
    anios = parsear_anios_experiencia(texto_mensaje)
    if anios is None:
        return {
            "success": True,
            "messages": [{"response": "*Necesito un numero de años de experiencia (ej: 5).*"}],
        }

    flujo["experience_years"] = anios
    if flujo.get("profile_edit_mode") == "experience":
        flujo.pop("profile_edit_mode", None)
        flujo["state"] = "awaiting_profile_completion_confirmation"
        return {
            "success": True,
            "messages": [
                payload_confirmacion_resumen(
                    construir_resumen_confirmacion_perfil_profesional(
                        experience_years=flujo.get("experience_years"),
                        social_media_url=flujo.get("social_media_url"),
                        certificate_uploaded=bool(flujo.get("certificate_uploaded")),
                        services=list(flujo.get("servicios_temporales") or []),
                    )
                )
            ],
        }
    if flujo.get("profile_completion_mode"):
        flujo["state"] = "awaiting_social_media"
        return {
            "success": True,
            "messages": [payload_red_social_opcional()],
        }

    flujo["state"] = "awaiting_email"
    return {
        "success": True,
        "messages": [
            {
                "response": "*Escribe tu correo electrónico o escribe \"omitir\" si no deseas agregarlo.*"
            }
        ],
    }
