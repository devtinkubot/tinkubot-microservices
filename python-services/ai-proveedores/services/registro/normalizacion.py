"""
Funciones de normalización de datos de proveedores.
"""
import logging
from typing import Any, Dict, Optional

from models.proveedores import SolicitudCreacionProveedor

from services.servicios_proveedor.utilidades import (
    formatear_servicios_a_cadena as formatear_servicios,
    normalizar_profesion_para_almacenamiento as normalizar_profesion_para_storage,
    normalizar_texto_para_busqueda,
    sanitizar_lista_servicios as sanitizar_servicios,
)

logger = logging.getLogger(__name__)


def normalizar_datos_proveedor(datos_crudos: SolicitudCreacionProveedor) -> Dict[str, Any]:
    """
    Normaliza datos del formulario para el esquema unificado.

    Args:
        datos_crudos: Datos crudos del proveedor desde el formulario

    Returns:
        Dict con datos normalizados según el esquema unificado
    """
    servicios_limpios = sanitizar_servicios(datos_crudos.services_list or [])
    return {
        "phone": datos_crudos.phone.strip(),
        "full_name": datos_crudos.full_name.strip().title(),  # Formato legible
        "email": datos_crudos.email.strip() if datos_crudos.email else None,
        "city": normalizar_texto_para_busqueda(datos_crudos.city),  # minúsculas
        "profession": normalizar_profesion_para_storage(
            datos_crudos.profession
        ),  # minúsculas y abreviaturas expandidas
        "services": formatear_servicios(servicios_limpios),
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

    Args:
        registro: Diccionario con datos del proveedor (puede estar incompleto)

    Returns:
        Dict con todos los campos obligatorios garantizados
    """
    datos = dict(registro or {})
    datos.setdefault("verified", False)

    available_value = datos.get("available")
    if available_value is None:
        available_value = datos.get("verified", True)
    datos["available"] = bool(available_value)

    datos["rating"] = float(datos.get("rating") or 5.0)
    datos["experience_years"] = int(datos.get("experience_years") or 0)
    datos["services"] = datos.get("services") or ""
    datos["has_consent"] = bool(datos.get("has_consent"))
    datos["status"] = "approved" if datos.get("verified") else "pending"
    return datos
