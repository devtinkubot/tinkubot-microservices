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


def validar_datos_registro_proveedor(
    phone: str,
    nombre: Optional[str],
    email: Optional[str],
    ciudad: Optional[str],
    profesion: Optional[str],
    especialidad: Optional[str],
    anios_experiencia: Optional[int],
    tiene_consentimiento: bool,
    url_red_social: Optional[str] = None,
    tipo_red_social: Optional[str] = None,
) -> Tuple[bool, Optional[str], Optional[SolicitudCreacionProveedor]]:
    """
    Valida los datos del formulario de registro de proveedor.

    Realiza validaciones usando Pydantic para garantizar que los datos
    cumplan con el esquema requerido antes de intentar el registro.

    Args:
        phone: Número de teléfono del proveedor
        nombre: Nombre completo del proveedor
        email: Correo electrónico (opcional)
        ciudad: Ciudad donde trabaja el proveedor
        profesion: Profesión del proveedor
        especialidad: Cadena de especialidades/servicios (puede estar separada por delimitadores)
        anios_experiencia: Años de experiencia (opcional)
        tiene_consentimiento: Si el proveedor dio consentimiento para el tratamiento de datos
        url_red_social: URL de red social (opcional)
        tipo_red_social: Tipo de red social (opcional)

    Returns:
        Tupla con:
        - bool: True si la validación fue exitosa
        - Optional[str]: Mensaje de error si la validación falló, None si fue exitosa
        - Optional[SolicitudCreacionProveedor]: Objeto SolicitudCreacionProveedor si la validación fue exitosa, None si falló
    """
    # Procesar lista de servicios desde la especialidad
    servicios_lista = _procesar_lista_servicios(especialidad)

    try:
        proveedor = SolicitudCreacionProveedor(
            phone=phone,
            full_name=nombre or "",
            email=email,
            city=ciudad or "",
            profession=profesion or "",
            services_list=servicios_lista,
            experience_years=anios_experiencia,
            has_consent=tiene_consentimiento,
            social_media_url=url_red_social,
            social_media_type=tipo_red_social,
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


def construir_proveedor_desde_formulario(
    datos_formulario: Dict[str, Any],
    phone: str,
) -> Tuple[bool, Optional[str], Optional[SolicitudCreacionProveedor]]:
    """
    Construye un objeto SolicitudCreacionProveedor desde los datos del formulario de flujo.

    Esta función extrae y transforma los datos del flujo conversacional
    en un objeto de dominio validado.

    Args:
        datos_formulario: Diccionario con todos los datos del flujo
        phone: Número de teléfono del proveedor

    Returns:
        Tupla con:
        - bool: True si la construcción fue exitosa
        - Optional[str]: Mensaje de error si falló, None si fue exitosa
        - Optional[SolicitudCreacionProveedor]: Objeto construido y validado
    """
    return validar_datos_registro_proveedor(
        phone=phone,
        nombre=datos_formulario.get("name"),
        email=datos_formulario.get("email"),
        ciudad=datos_formulario.get("city"),
        profesion=datos_formulario.get("profession"),
        especialidad=datos_formulario.get("specialty"),
        anios_experiencia=datos_formulario.get("experience_years"),
        tiene_consentimiento=datos_formulario.get("has_consent", False),
        url_red_social=datos_formulario.get("social_media_url"),
        tipo_red_social=datos_formulario.get("social_media_type"),
    )


def validar_y_construir_proveedor(
    flow: Dict[str, Any],
    phone: str,
) -> Tuple[bool, Optional[str], Optional[SolicitudCreacionProveedor]]:
    """
    Función principal que valida y construye un proveedor desde el flujo.

    Esta es la función de conveniencia principal que combina la extracción
    de datos del flujo con la validación y construcción del objeto.

    Args:
        flow: Diccionario del flujo conversacional
        phone: Número de teléfono del proveedor

    Returns:
        Tupla con:
        - bool: True si la validación y construcción fueron exitosas
        - Optional[str]: Mensaje de error si falló, None si fue exitosa
        - Optional[SolicitudCreacionProveedor]: Objeto construido y validado
    """
    return construir_proveedor_desde_formulario(flow, phone)


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
        "full_name": "nombre",
        "email": "correo electrónico",
        "city": "ciudad",
        "profession": "profesión",
        "services_list": "servicios",
        "experience_years": "años de experiencia",
        "has_consent": "consentimiento",
    }

    campo_espanol = nombres_campos.get(campo, campo)

    return f"{campo_espanol}: {mensaje}"
