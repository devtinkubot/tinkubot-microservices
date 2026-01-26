"""
Utilidad para extracción de servicios almacenados.
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


def extraer_servicios_almacenados(valor: Optional[str]) -> List[str]:
    """
    Convierte la cadena almacenada en lista de servicios.

    Extrae servicios desde una cadena almacenada en base de datos,
    eliminando duplicados y respetando el límite máximo de servicios.

    Args:
        valor: Cadena con servicios separados por delimitadores.

    Returns:
        Lista de servicios únicos, limitada a SERVICIOS_MAXIMOS.
    """
    if not valor:
        return []

    cleaned = valor.strip()
    if not cleaned:
        return []

    servicios = dividir_cadena_servicios(cleaned)
    # Mantener máximo permitido y eliminar duplicados preservando orden
    resultado: List[str] = []
    for servicio in servicios:
        if servicio not in resultado:
            resultado.append(servicio)
        if len(resultado) >= SERVICIOS_MAXIMOS:
            break
    return resultado
