"""
Gestor de resultados de búsqueda de proveedores.

Este módulo contiene funciones para construir mensajes de resultados
de búsqueda, ya sea con proveedores encontrados o sin resultados.
"""

import logging
from typing import Any, Dict, List

from templates.proveedores.detalle import instruccion_seleccionar_proveedor
from templates.proveedores.listado import (
    bloque_listado_proveedores_compacto,
    mensaje_intro_listado_proveedores,
    mensaje_listado_sin_resultados,
)

logger = logging.getLogger(__name__)


def construir_mensajes_resultados(
    proveedores: List[Dict[str, Any]], ciudad: str
) -> List[str]:
    """
    Construye mensajes para presentar resultados cuando hay proveedores.

    Genera un listado compacto de proveedores con instrucciones de selección.

    Args:
        proveedores: Lista de proveedores encontrados (máximo 5).
        ciudad: Ciudad donde se encontraron los proveedores.

    Returns:
        Lista con un único mensaje conteniendo el listado de proveedores.

    Example:
        >>> proveedores = [
        ...     {"name": "Juan Pérez", "profession": "plomero"},
        ...     {"name": "María García", "profession": "plomero"}
        ... ]
        >>> mensajes = construir_mensajes_resultados(proveedores, "Madrid")
        >>> len(mensajes)
        1
        >>> "Juan Pérez" in mensajes[0]
        True
    """
    if not proveedores:
        logger.warning("⚠️ construir_mensajes_resultados llamado sin proveedores")
        return []

    try:
        intro = mensaje_intro_listado_proveedores(ciudad)
        bloque = bloque_listado_proveedores_compacto(proveedores)
        bloque_encabezado = (
            f"{intro}\n\n{bloque}\n{instruccion_seleccionar_proveedor}"
        )

        logger.info(
            f"✅ Mensaje de resultados construido: {len(proveedores)} proveedores"
        )

        return [bloque_encabezado]

    except Exception as exc:
        logger.error(f"❌ Error construyendo mensajes de resultados: {exc}")
        return []


def construir_mensajes_sin_resultados(ciudad: str) -> List[str]:
    """
    Construye mensajes para presentar cuando no hay resultados.

    Genera un mensaje informando que no hay proveedores disponibles
    en la ciudad especificada.

    Args:
        ciudad: Ciudad donde se buscó proveedores.

    Returns:
        Lista con un único mensaje sin resultados.

    Example:
        >>> mensajes = construir_mensajes_sin_resultados("Madrid")
        >>> len(mensajes)
        1
        >>> "No tenemos" in mensajes[0]
        True
    """
    try:
        bloque = mensaje_listado_sin_resultados(ciudad)

        logger.info(f"✅ Mensaje sin resultados construido para city='{ciudad}'")

        return [bloque]

    except Exception as exc:
        logger.error(f"❌ Error construyendo mensaje sin resultados: {exc}")
        return [mensaje_listado_sin_resultados(ciudad)]


def construir_resumen_resultados(proveedores: List[Dict[str, Any]]) -> str:
    """
    Construye un resumen breve de los resultados encontrados.

    Args:
        proveedores: Lista de proveedores encontrados.

    Returns:
        String con resumen de cantidad y nombres de proveedores.

    Example:
        >>> proveedores = [
        ...     {"name": "Juan Pérez"},
        ...     {"name": "María García"}
        ... ]
        >>> resumen = construir_resumen_resultados(proveedores)
        >>> "2 proveedores" in resumen
        True
    """
    if not proveedores:
        return "No se encontraron proveedores"

    cantidad = len(proveedores)
    if cantidad == 1:
        nombre = proveedores[0].get("name", "Proveedor")
        return f"1 proveedor encontrado: {nombre}"
    nombres = [p.get("name", "Proveedor") for p in proveedores[:3]]
    nombres_texto = ", ".join(nombres)
    if cantidad > 3:
        return f"{cantidad} proveedores encontrados: {nombres_texto} y otros..."
    return f"{cantidad} proveedores encontrados: {nombres_texto}"
