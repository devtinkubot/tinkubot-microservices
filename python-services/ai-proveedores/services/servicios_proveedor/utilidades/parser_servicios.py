"""
Utilidad para parseo de servicios con validación completa.
"""

from typing import List, Optional

import sys
from pathlib import Path

# Agregar el directorio raíz al sys.path para imports absolutos
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from services.servicios_proveedor.constantes import SERVICIOS_MAXIMOS
from services.servicios_proveedor.utilidades.divisor_cadena_servicios import (
    dividir_cadena_servicios,
)
from services.servicios_proveedor.utilidades.normalizador_texto_busqueda import (
    normalizar_texto_para_busqueda,
)


def parsear_servicios_con_limite(
    value: Optional[str],
    maximos: int = SERVICIOS_MAXIMOS,
    normalizar: bool = False,
) -> List[str]:
    """
    Parsea una cadena de servicios con validación completa.

    Función unificada que:
    - Divide por separadores (| , ; / \\n)
    - Normaliza cada servicio (strip, minúsculas) si se solicita
    - Elimina duplicados manteniendo orden
    - Limita a maximos elementos

    Es la función recomendada para procesar entrada de usuario con validaciones.

    Args:
        value: Cadena con servicios separados por |, ;, ,, / o saltos de línea.
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
