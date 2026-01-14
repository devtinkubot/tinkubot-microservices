"""Servicio de interpretación de respuestas de usuario."""
import unicodedata
from typing import Optional


def interpretar_opcion_menu(text: Optional[str]) -> Optional[str]:
    """
    Interpretar respuesta de menú (opciones 1-5).

    Args:
        text: Texto a interpretar

    Returns:
        "1", "2", "3", "4", "5" o None si no es reconocido
    """
    value = (text or "").strip().lower()
    if not value:
        return None

    # Normalización
    normalized_value = unicodedata.normalize("NFKD", value)
    normalized_value = normalized_value.encode("ascii", "ignore").decode().strip()

    if not normalized_value:
        return None

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

    # Opción 4 - Salir
    if (
        normalized_value.startswith("4")
        or normalized_value.startswith("cuatro")
        or "salir" in normalized_value
        or "terminar" in normalized_value
        or "menu" in normalized_value
        or "volver" in normalized_value
    ):
        return "4"

    # Opción 5 - Eliminar registro
    if (
        normalized_value.startswith("5")
        or normalized_value.startswith("cinco")
        or "eliminar" in normalized_value
        or "borrar" in normalized_value
        or "delete" in normalized_value
        or "eliminar mi" in normalized_value
        or "eliminar registro" in normalized_value
    ):
        return "5"

    return None


def interpretar_consentimiento(text: Optional[str]) -> Optional[bool]:
    """
    Interpretar respuesta de consentimiento (sí/no).

    Args:
        text: Texto a interpretar

    Returns:
        True para afirmativo, False para negativo, None si no es reconocido
    """
    value = (text or "").strip().lower()
    if not value:
        return None

    # Normalización
    normalized_value = unicodedata.normalize("NFKD", value)
    normalized_value = normalized_value.encode("ascii", "ignore").decode().strip()

    if not normalized_value:
        return None

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


def interpretar_respuesta_usuario(
    text: Optional[str], modo: str = "menu"
) -> Optional[object]:
    """
    Interpretar respuesta del usuario unificando menú y consentimiento.

    Esta función mantiene compatibilidad hacia atrás. Nuevo código debería usar
    interpretar_opcion_menu() o interpretar_consentimiento() directamente.

    Args:
        text: Texto a interpretar
        modo: "menu" para opciones 1-5, "consentimiento" para sí/no

    Returns:
        - modo="menu": "1", "2", "3", "4", "5" o None
        - modo="consentimiento": True, False o None
    """
    if modo == "consentimiento":
        return interpretar_consentimiento(text)
    if modo == "menu":
        return interpretar_opcion_menu(text)
    return None
