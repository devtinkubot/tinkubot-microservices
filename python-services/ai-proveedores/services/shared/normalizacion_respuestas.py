"""Normalización compartida de respuestas de usuario."""

from __future__ import annotations

import logging
import unicodedata
from typing import Optional

logger = logging.getLogger(__name__)


def interpretar_respuesta(text: Optional[str], modo: str = "menu") -> Optional[object]:
    """Interpretar respuesta del usuario unificando menú y consentimiento."""
    value = (text or "").strip().lower()
    if not value:
        return None

    normalized_value = unicodedata.normalize("NFKD", value)
    normalized_value = normalized_value.encode("ascii", "ignore").decode().strip()

    if not normalized_value:
        return None

    if normalized_value.startswith("provider_menu_") or normalized_value.startswith(
        "provider_submenu_"
    ):
        return None

    if modo == "consentimiento":
        if normalized_value.startswith("1"):
            return True
        if normalized_value.startswith("2"):
            return False

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

    if modo == "menu":
        if (
            normalized_value.startswith("1")
            or normalized_value.startswith("uno")
            or "servicio" in normalized_value
            or "servicios" in normalized_value
            or "gestionar" in normalized_value
        ):
            return "1"

        if (
            normalized_value.startswith("2")
            or normalized_value.startswith("dos")
            or "selfie" in normalized_value
            or "foto" in normalized_value
            or "selfis" in normalized_value
            or "photo" in normalized_value
        ):
            return "2"

        if (
            normalized_value.startswith("3")
            or normalized_value.startswith("tres")
            or "red" in normalized_value
            or "social" in normalized_value
            or "instagram" in normalized_value
            or "facebook" in normalized_value
        ):
            return "3"

        if (
            normalized_value.startswith("4")
            or normalized_value.startswith("cuatro")
            or "eliminar" in normalized_value
            or "borrar" in normalized_value
            or "delete" in normalized_value
        ):
            return "4"

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

    return None
