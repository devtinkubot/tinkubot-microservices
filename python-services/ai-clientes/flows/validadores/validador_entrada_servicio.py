"""Módulo de validación de entrada de servicio."""

import re

from templates.mensajes.validacion import (
    mensaje_error_input_invalido,
    solicitar_descripcion_servicio,
)


def validar_entrada_servicio(
    texto: str,
    saludos: set[str],
    catalogo_servicios: dict[str, set[str]],
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
    texto_limpio = (texto or "").strip()

    # Caso 1: Vacío o saludo
    if not texto_limpio or texto_limpio.lower() in saludos:
        return False, solicitar_descripcion_servicio()

    # Caso 2: Solo números
    if texto_limpio.isdigit():
        return False, mensaje_error_input_invalido

    # Caso 3: Letra suelta
    if re.fullmatch(r"[a-zA-Z]", texto_limpio):
        return False, mensaje_error_input_invalido

    # Caso 4: Demasiado corto
    palabras = texto_limpio.split()
    if len(palabras) < 2 and len(texto_limpio) < 4:
        return False, mensaje_error_input_invalido

    # Caso 5: Es servicio reconocido
    normalizado = texto_limpio.lower()
    for _, sinonimos in catalogo_servicios.items():
        if normalizado in {s.lower() for s in sinonimos}:
            return True, ""

    # Caso 6: Tiene >= 2 palabras (válido, pasará a extracción)
    if len(palabras) >= 2:
        return True, ""

    # Caso 7: Inválido por defecto
    return False, mensaje_error_input_invalido
