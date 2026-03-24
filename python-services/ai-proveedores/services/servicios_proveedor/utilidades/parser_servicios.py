"""Utilidades para parseo de servicios con validación completa."""

import re
from typing import List, Optional

from ..constantes import SERVICIOS_MAXIMOS
from .divisor_cadena_servicios import dividir_cadena_servicios
from .normalizador_texto_busqueda import normalizar_texto_para_busqueda

_NUMERO_SERVICIO_PATTERN = re.compile(r"(?<!\d)(\d{1,2})(?=\s)")


def parsear_servicios_con_limite(
    value: Optional[str],
    maximos: int = SERVICIOS_MAXIMOS,
    normalizar: bool = False,
) -> List[str]:
    """
    Parsea una cadena de servicios con validación completa.

    Función unificada que:
    - Divide por separadores (| ; / \\n)
    - Normaliza cada servicio (strip, minúsculas) si se solicita
    - Elimina duplicados manteniendo orden
    - Limita a maximos elementos

    Es la función recomendada para procesar entrada de usuario con validaciones.

    Args:
        value: Cadena con servicios separados por |, ;, / o saltos de línea.
        maximos: Cantidad máxima de servicios a retornar (default: SERVICIOS_MAXIMOS).
        normalizar: Si True, aplica normalización completa (minúsculas, sin acentos).

    Returns:
        Lista de servicios únicos, normalizados si se solicitó, limitada a maximos.

    Example:
        >>> parsear_servicios_con_limite("Plomería; electricidad | Albañilería")
        ['Plomería', 'electricidad', 'Albañilería']

        >>> parsear_servicios_con_limite("A; B; A; C", maximos=2)
        ['A', 'B']
    """
    if not value:
        return []

    # Dividir usando la función base
    candidatos = dividir_cadena_servicios(value)
    if not candidatos:
        return []

    servicios_unicos: List[str] = []
    for candidato in candidatos:
        # Aplicar normalización si se solicita
        servicio = (
            normalizar_texto_para_busqueda(candidato)
            if normalizar
            else candidato.strip()
        )

        # Solo agregar si no está vacío y no es duplicado
        if servicio and servicio not in servicios_unicos:
            servicios_unicos.append(servicio)

        # Respetar límite máximo
        if len(servicios_unicos) >= maximos:
            break

    return servicios_unicos


def parsear_servicios_numerados_con_limite(
    value: Optional[str],
    maximos: int = SERVICIOS_MAXIMOS,
) -> List[str]:
    """Parses a compact numbered block like ``1 foo 2 bar 3 baz``.

    The sequence must start at ``1`` and increment by one without gaps.
    The numeric marker must be followed by whitespace only.
    Returns an empty list when the block does not match the expected format.
    """
    if not value:
        return []

    texto = value.strip()
    if not texto:
        return []

    coincidencias = list(_NUMERO_SERVICIO_PATTERN.finditer(texto))
    if not coincidencias:
        return []

    servicios: List[str] = []
    numero_esperado = 1

    for idx, coincidencia in enumerate(coincidencias):
        numero_actual = int(coincidencia.group(1))
        if numero_actual != numero_esperado:
            return []

        inicio = coincidencia.end()
        fin = coincidencias[idx + 1].start() if idx + 1 < len(coincidencias) else len(texto)
        candidato = " ".join(texto[inicio:fin].strip().split())
        if not candidato:
            return []

        if candidato not in servicios:
            servicios.append(candidato)
        numero_esperado += 1
        if len(servicios) >= maximos:
            break

    return servicios
