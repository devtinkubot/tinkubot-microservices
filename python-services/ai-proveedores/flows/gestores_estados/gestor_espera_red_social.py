"""Manejador del estado awaiting_social_media."""

from typing import Any, Dict, Optional

from flows.validadores.validador_entrada import parsear_entrada_red_social
from templates.registro import (
    SOCIAL_SKIP_ID,
    construir_resumen_confirmacion_perfil_profesional,
    payload_certificado_opcional,
    payload_confirmacion_resumen,
)


def manejar_espera_red_social(
    flujo: Dict[str, Any], texto_mensaje: Optional[str]
) -> Dict[str, Any]:
    """Procesa la entrada del usuario para el campo red social.

    Args:
        flujo: Diccionario del flujo conversacional.
        texto_mensaje: Mensaje del usuario con la red social.

    Returns:
        Respuesta con éxito y siguiente pregunta.
    """
    texto_normalizado = (texto_mensaje or "").strip()
    if texto_normalizado.lower() == SOCIAL_SKIP_ID:
        texto_normalizado = "omitir"

    red_social_parseada = parsear_entrada_red_social(texto_normalizado)
    flujo["social_media_url"] = red_social_parseada["url"]
    flujo["social_media_type"] = red_social_parseada["type"]

    if flujo.get("profile_edit_mode") == "social_media":
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
        flujo["state"] = "awaiting_certificate"
        return {"success": True, "messages": [payload_certificado_opcional()]}

    flujo["state"] = "awaiting_dni_front_photo"
    return {
        "success": True,
        "messages": [
            {
                "response": (
                    "*Para validar tu identidad y mantener la confianza en la "
                    "plataforma*, necesito una foto clara de la parte frontal de "
                    "tu cédula. *Envíala como imagen adjunta.*"
                )
            }
        ],
    }
