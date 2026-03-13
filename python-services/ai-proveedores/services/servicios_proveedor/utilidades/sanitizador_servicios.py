"""Utilidad para sanitización de listas de servicios."""

from typing import List, Optional

import sys
from pathlib import Path

# Agregar el directorio raíz al sys.path para imports absolutos
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from services.servicios_proveedor.constantes import SERVICIOS_MAXIMOS
from services.servicios_proveedor.utilidades.limpiador_servicio import limpiar_texto_servicio
from services.servicios_proveedor.utilidades.normalizador_texto_busqueda import (
    normalizar_texto_para_busqueda,
)


def sanitizar_lista_servicios(lista_servicios: Optional[List[str]]) -> List[str]:
    """
    Genera lista única de servicios limpios, limitada a SERVICIOS_MAXIMOS.

    Procesa una lista de servicios eliminando duplicados y ruido, pero
    preservando el texto natural para UI, embeddings y trazabilidad.

    Args:
        lista_servicios: Lista de descripciones de servicios a sanitizar.

    Returns:
        Lista de servicios únicos y normalizados, limitada a SERVICIOS_MAXIMOS elementos.
    """
    servicios_limpios: List[str] = []
    claves_vistas = set()
    if not lista_servicios:
        return servicios_limpios

    for servicio in lista_servicios:
        texto_visible = " ".join(str(servicio or "").strip().split())
        if not texto_visible:
            continue

        clave_dedupe = limpiar_texto_servicio(texto_visible)
        if not clave_dedupe:
            clave_dedupe = normalizar_texto_para_busqueda(texto_visible)

        if not clave_dedupe or clave_dedupe in claves_vistas:
            continue
        claves_vistas.add(clave_dedupe)
        servicios_limpios.append(texto_visible)
        if len(servicios_limpios) >= SERVICIOS_MAXIMOS:
            break

    return servicios_limpios
