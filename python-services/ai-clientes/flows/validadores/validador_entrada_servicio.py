"""Módulo de validación de entrada de servicio."""

import re

from templates.mensajes.validacion import (
    mensaje_error_input_invalido,
    solicitar_descripcion_servicio,
)


def validar_entrada_servicio(
    text: str,
    greetings: set[str],
    service_catalog: dict[str, set[str]]
) -> tuple[bool, str]:
    """
    Valida que el input sea estructurado y significativo.

    Retorna: (is_valid, error_message)

    Casos de rechazo:
    - Vacío o saludo
    - Solo números
    - Letra suelta
    - Demasiado corto

    Casos de aceptación:
    - Servicio reconocido del catálogo
    - >= 2 palabras (pasa a extracción)
    """
    cleaned = (text or "").strip()

    # Caso 1: Vacío o saludo
    if not cleaned or cleaned.lower() in greetings:
        return False, solicitar_descripcion_servicio()

    # Caso 2: Solo números
    if cleaned.isdigit():
        return False, mensaje_error_input_invalido

    # Caso 3: Letra suelta
    if re.fullmatch(r"[a-zA-Z]", cleaned):
        return False, mensaje_error_input_invalido

    # Caso 4: Demasiado corto
    words = cleaned.split()
    if len(words) < 2 and len(cleaned) < 4:
        return False, mensaje_error_input_invalido

    # Caso 5: Es servicio reconocido
    normalized = cleaned.lower()
    for _, synonyms in service_catalog.items():
        if normalized in {s.lower() for s in synonyms}:
            return True, ""

    # Caso 6: Tiene >= 2 palabras (válido, pasará a extracción)
    if len(words) >= 2:
        return True, ""

    # Caso 7: Inválido por defecto
    return False, mensaje_error_input_invalido
