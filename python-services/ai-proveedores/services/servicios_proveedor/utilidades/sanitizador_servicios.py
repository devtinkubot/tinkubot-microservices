"""
Utilidad para sanitización de listas de servicios.
"""

from typing import List, Optional

import sys
from pathlib import Path

# Agregar el directorio raíz al sys.path para imports absolutos
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from services.servicios_proveedor.constantes import SERVICIOS_MAXIMOS
from services.servicios_proveedor.utilidades.limpiador_servicio import (
    limpiar_texto_servicio,
)


def sanitizar_lista_servicios(lista_servicios: Optional[List[str]]) -> List[str]:
    """
    Genera lista única de servicios limpios, limitada a SERVICIOS_MAXIMOS.

    Procesa una lista de servicios, eliminando duplicados, aplicando
    normalización y limitando la cantidad máxima de servicios.

    Args:
        lista_servicios: Lista de descripciones de servicios a sanitizar.

    Returns:
        Lista de servicios únicos y normalizados, limitada a SERVICIOS_MAXIMOS elementos.
    """
    servicios_limpios: List[str] = []
    if not lista_servicios:
        return servicios_limpios

    for servicio in lista_servicios:
        texto = limpiar_texto_servicio(servicio)
        if not texto or texto in servicios_limpios:
            continue
        servicios_limpios.append(texto)
        if len(servicios_limpios) >= SERVICIOS_MAXIMOS:
            break

    return servicios_limpios
