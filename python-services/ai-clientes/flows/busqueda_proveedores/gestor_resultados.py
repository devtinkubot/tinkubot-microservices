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
    providers: List[Dict[str, Any]], city: str
) -> List[str]:
    """
    Construye mensajes para presentar resultados cuando hay proveedores.

    Genera un listado compacto de proveedores con instrucciones de selección.

    Args:
        providers: Lista de proveedores encontrados (máximo 5).
        city: Ciudad donde se encontraron los proveedores.

    Returns:
        Lista con un único mensaje conteniendo el listado de proveedores.

    Example:
        >>> providers = [
        ...     {"name": "Juan Pérez", "profession": "plomero"},
        ...     {"name": "María García", "profession": "plomero"}
        ... ]
        >>> mensajes = construir_mensajes_resultados(providers, "Madrid")
        >>> len(mensajes)
        1
        >>> "Juan Pérez" in mensajes[0]
        True
    """
    if not providers:
        logger.warning("⚠️ construir_mensajes_resultados llamado sin proveedores")
        return []

    try:
        intro = mensaje_intro_listado_proveedores(city)
        block = bloque_listado_proveedores_compacto(providers)
        header_block = f"{intro}\n\n{block}\n{instruccion_seleccionar_proveedor}"

        logger.info(
            f"✅ Mensaje de resultados construido: {len(providers)} proveedores"
        )

        return [header_block]

    except Exception as exc:
        logger.error(f"❌ Error construyendo mensajes de resultados: {exc}")
        return []


def construir_mensajes_sin_resultados(city: str) -> List[str]:
    """
    Construye mensajes para presentar cuando no hay resultados.

    Genera un mensaje informando que no hay proveedores disponibles
    en la ciudad especificada.

    Args:
        city: Ciudad donde se buscó proveedores.

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
        block = mensaje_listado_sin_resultados(city)

        logger.info(f"✅ Mensaje sin resultados construido para city='{city}'")

        return [block]

    except Exception as exc:
        logger.error(f"❌ Error construyendo mensaje sin resultados: {exc}")
        return [mensaje_listado_sin_resultados(city)]


def construir_resumen_resultados(providers: List[Dict[str, Any]]) -> str:
    """
    Construye un resumen breve de los resultados encontrados.

    Args:
        providers: Lista de proveedores encontrados.

    Returns:
        String con resumen de cantidad y nombres de proveedores.

    Example:
        >>> providers = [
        ...     {"name": "Juan Pérez"},
        ...     {"name": "María García"}
        ... ]
        >>> resumen = construir_resumen_resultados(providers)
        >>> "2 proveedores" in resumen
        True
    """
    if not providers:
        return "No se encontraron proveedores"

    cantidad = len(providers)
    if cantidad == 1:
        nombre = providers[0].get("name", "Proveedor")
        return f"1 proveedor encontrado: {nombre}"
    else:
        nombres = [p.get("name", "Proveedor") for p in providers[:3]]
        nombres_text = ", ".join(nombres)
        if cantidad > 3:
            return f"{cantidad} proveedores encontrados: {nombres_text} y otros..."
        return f"{cantidad} proveedores encontrados: {nombres_text}"
