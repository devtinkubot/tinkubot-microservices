"""
Servicio de validación de registro de proveedores.

Este módulo contiene la lógica de negocio para:
- Validar datos del formulario de registro
- Construir objetos SolicitudCreacionProveedor desde datos de flujo
- Manejar errores de validación de forma robusta

Responsabilidades:
- Validación de datos de entrada usando Pydantic
- Construcción de objetos de dominio
- Lógica de negocio separada de la presentación
"""
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError
from models.proveedores import SolicitudCreacionProveedor

logger = logging.getLogger(__name__)


def validar_y_construir_proveedor(
    flujo: Dict[str, Any],
    telefono: str,
) -> Tuple[bool, Optional[str], Optional[SolicitudCreacionProveedor]]:
    """
    Función principal que valida y construye un proveedor desde el flujo.

    Esta función extrae los datos del flujo conversacional y construye
    un objeto SolicitudCreacionProveedor validado.

    Args:
        flujo: Diccionario del flujo conversacional
        telefono: Número de teléfono del proveedor

    Returns:
        Tupla con:
        - bool: True si la validación y construcción fueron exitosas
        - Optional[str]: Mensaje de error si falló, None si fue exitosa
        - Optional[SolicitudCreacionProveedor]: Objeto construido y validado
    """
    # Procesar lista de servicios desde la especialidad
    especialidad = flujo.get("specialty")
    servicios_lista = _procesar_lista_servicios(especialidad)

    try:
        proveedor = SolicitudCreacionProveedor(
            phone=telefono,
            real_phone=flujo.get("real_phone") or telefono,
            full_name=flujo.get("name") or "",
            email=flujo.get("email"),
            city=flujo.get("city") or "",
            # Fase 4: Eliminado campo profession - ya no existe en el modelo
            services_list=servicios_lista,
            experience_years=flujo.get("experience_years"),
            has_consent=flujo.get("has_consent", False),
            social_media_url=flujo.get("social_media_url"),
            social_media_type=flujo.get("social_media_type"),
        )
        return True, None, proveedor

    except ValidationError as exc:
        logger.error("Error de validación en datos de registro: %s", exc)
        primer_error = exc.errors()[0] if exc.errors() else {}
        mensaje_error = _formatear_mensaje_error_validacion(primer_error)
        return False, mensaje_error, None

    except Exception as exc:
        logger.error("Error inesperado al validar datos de registro: %s", exc)
        return False, "Error inesperado al validar los datos", None


def _procesar_lista_servicios(especialidad: Optional[str]) -> List[str]:
    """
    Procesa la cadena de especialidad para extraer lista de servicios.

    Args:
        especialidad: Cadena que puede contener múltiples servicios separados
                      por delimitadores como ;, /, o saltos de línea

    Returns:
        Lista de servicios limpia y sin duplicados
    """
    if not especialidad or not isinstance(especialidad, str):
        return []

    servicios = [
        item.strip()
        for item in re.split(r"[;,/\n]+", especialidad)
        if item and item.strip()
    ]

    # Si no se encontraron delimitadores pero hay contenido, usar toda la cadena
    if not servicios and especialidad.strip():
        servicios = [especialidad.strip()]

    return servicios


def _formatear_mensaje_error_validacion(error: Dict[str, Any]) -> str:
    """
    Formatea un error de validación de Pydantic en un mensaje legible.

    Args:
        error: Diccionario de error de Pydantic

    Returns:
        Mensaje de error formateado para el usuario
    """
    if not error:
        return "Datos inválidos"

    campo = error.get("loc", ["campo"])[0]
    mensaje = error.get("msg", "valor inválido")

    # Mapeo de campos a nombres en español
    nombres_campos = {
        "phone": "teléfono",
        "real_phone": "teléfono real",
        "full_name": "nombre",
        "email": "correo electrónico",
        "city": "ciudad",
        # Fase 4: Eliminada referencia a profession del mapeo
        "services_list": "servicios",
        "experience_years": "años de experiencia",
        "has_consent": "consentimiento",
    }

    campo_espanol = nombres_campos.get(campo, campo)

    return f"{campo_espanol}: {mensaje}"
