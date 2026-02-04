"""
Funciones de normalización de datos de proveedores.
"""
import logging
from typing import Any, Dict, Optional

from models.proveedores import SolicitudCreacionProveedor

from services.servicios_proveedor.utilidades import (
    normalizar_texto_para_busqueda,
    sanitizar_lista_servicios as sanitizar_servicios,
)

logger = logging.getLogger(__name__)


def normalizar_datos_proveedor(datos_crudos: SolicitudCreacionProveedor) -> Dict[str, Any]:
    """
    Normaliza datos del formulario para el esquema unificado.

    Fase 5: Eliminado campo 'profession' y actualizada lógica de servicios.
    Ahora se retorna una lista de servicios normalizados en lugar de un string formateado.

    Args:
        datos_crudos: Datos crudos del proveedor desde el formulario

    Returns:
        Dict con datos normalizados según el esquema unificado

    Raises:
        ValueError: Si no hay servicios o más de 5 servicios
    """
    # Fase 5: Validar cantidad de servicios
    servicios = datos_crudos.services_list or []
    if len(servicios) == 0:
        raise ValueError("Debe ingresar al menos 1 servicio")
    if len(servicios) > 5:
        raise ValueError("Máximo 5 servicios permitidos")

    # Fase 5: Normalizar servicios (title case, trim)
    servicios_limpios = sanitizar_servicios(servicios)
    servicios_normalizados = [s.strip().title() for s in servicios_limpios if s.strip()]

    # Fase 5: Validar que después de la normalización quede al menos 1 servicio
    if len(servicios_normalizados) == 0:
        raise ValueError("Debe ingresar al menos 1 servicio válido")

    return {
        "phone": datos_crudos.phone.strip(),
        "full_name": datos_crudos.full_name.strip().title(),  # Formato legible
        "email": datos_crudos.email.strip() if datos_crudos.email else None,
        "city": normalizar_texto_para_busqueda(datos_crudos.city),  # minúsculas
        # Fase 5: Eliminado campo 'profession'
        "services_normalized": servicios_normalizados,  # Fase 5: Lista, no string
        "experience_years": datos_crudos.experience_years or 0,
        "has_consent": datos_crudos.has_consent,
        "verified": False,
        # Arrancamos en 5 para promediar con futuras calificaciones de clientes.
        "rating": 5.0,
        "social_media_url": datos_crudos.social_media_url,
        "social_media_type": datos_crudos.social_media_type,
    }


def garantizar_campos_obligatorios_proveedor(
    registro: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Garantiza que los campos obligatorios existan aunque la tabla no los tenga.

    Esta función aplica valores por defecto a campos opcionales o faltantes
    para asegurar consistencia en los datos de proveedores.

    Fase 5: Eliminadas referencias a 'profession'.

    Args:
        registro: Diccionario con datos del proveedor (puede estar incompleto)

    Returns:
        Dict con todos los campos obligatorios garantizados
    """
    datos = dict(registro or {})
    datos.setdefault("verified", False)

    valor_disponible = datos.get("available")
    if valor_disponible is None:
        valor_disponible = datos.get("verified", True)
    datos["available"] = bool(valor_disponible)

    datos["rating"] = float(datos.get("rating") or 5.0)
    datos["experience_years"] = int(datos.get("experience_years") or 0)
    # Fase 5: Eliminada referencia a 'profession'
    datos["has_consent"] = bool(datos.get("has_consent"))
    datos["status"] = "approved" if datos.get("verified") else "pending"
    return datos
