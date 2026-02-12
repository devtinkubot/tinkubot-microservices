"""
Intérprete de respuestas del usuario.

Este módulo contiene la lógica para interpretar las respuestas
textuales del usuario, tanto para opciones de menú como para
respuestas de sí/no en contextos de consentimiento.
"""

import logging
import unicodedata
from typing import Optional

logger = logging.getLogger(__name__)


def interpretar_respuesta(text: Optional[str], modo: str = "menu") -> Optional[object]:
    """
    Interpretar respuesta del usuario unificando menú y consentimiento.

    Args:
        text: Texto a interpretar
        modo: "menu" para opciones 1-5, "consentimiento" para sí/no

    Returns:
        - modo="menu": "1", "2", "3", "4", "5" o None
        - modo="consentimiento": True, False o None
    """
    value = (text or "").strip().lower()
    if not value:
        return None

    # Normalización unificada
    normalized_value = unicodedata.normalize("NFKD", value)
    normalized_value = normalized_value.encode("ascii", "ignore").decode().strip()

    if not normalized_value:
        return None

    # Modo consentimiento (sí/no)
    if modo == "consentimiento":
        affirmative = {
            "1",
            "si",
            "s",
            "acepto",
            "autorizo",
            "confirmo",
            "claro",
            "de acuerdo",
        }
        negative = {"2", "no", "n", "rechazo", "rechazar", "declino", "no autorizo"}

        if normalized_value in affirmative:
            return True
        if normalized_value in negative:
            return False
        return None

    # Modo menú (opciones 1-5)
    if modo == "menu":
        # Opción 1 - Gestionar servicios
        if (
            normalized_value.startswith("1")
            or normalized_value.startswith("uno")
            or "servicio" in normalized_value
            or "servicios" in normalized_value
            or "gestionar" in normalized_value
        ):
            return "1"

        # Opción 2 - Selfie
        if (
            normalized_value.startswith("2")
            or normalized_value.startswith("dos")
            or "selfie" in normalized_value
            or "foto" in normalized_value
            or "selfis" in normalized_value
            or "photo" in normalized_value
        ):
            return "2"

        # Opción 3 - Redes sociales
        if (
            normalized_value.startswith("3")
            or normalized_value.startswith("tres")
            or "red" in normalized_value
            or "social" in normalized_value
            or "instagram" in normalized_value
            or "facebook" in normalized_value
        ):
            return "3"

        # Opción 4 - Eliminar registro
        if (
            normalized_value.startswith("4")
            or normalized_value.startswith("cuatro")
            or "eliminar" in normalized_value
            or "borrar" in normalized_value
            or "delete" in normalized_value
        ):
            return "4"

        # Opción 5 - Salir
        if (
            normalized_value.startswith("5")
            or normalized_value.startswith("cinco")
            or "salir" in normalized_value
            or "terminar" in normalized_value
            or "menu" in normalized_value
            or "volver" in normalized_value
        ):
            return "5"

        return None

    # Modo no reconocido
    return None
