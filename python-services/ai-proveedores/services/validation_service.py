"""Servicio de validación de datos de proveedores."""
import logging
import re
from typing import Any, Dict, Optional, Tuple

from pydantic import ValidationError
from models.schemas import ProviderCreate

from services.parser_service import (
    normalize_text,
    OMISSION_VALUES,
)

logger = logging.getLogger(__name__)

# Constantes de validación
MIN_CIUDAD_CHARS = 2
MIN_NOMBRE_CHARS = 2
MIN_PROFESION_CHARS = 2
MAX_PROFESION_CHARS = 150
MIN_ESPECIALIDAD_CHARS = 2
MAX_ESPECIALIDAD_CHARS = 300
MAX_SERVICIO_CHARS = 120

# Límite de servicios por proveedor (unificado con utils/services_utils.py)
# La lógica de negocio establece un máximo de 5 servicios para mantener
# la calidad y foco en los servicios principales de cada proveedor
from utils.services_utils import SERVICIOS_MAXIMOS


def validate_city(city: str) -> Tuple[bool, Optional[str]]:
    """
    Valida ciudad del proveedor contra lista de ciudades ecuatorianas.

    Validaciones:
    - Debe ser una ciudad de Ecuador reconocida
    - No permite números ni signos (solo letras y espacios)
    - Normaliza a mayúscula inicial (Title Case)

    Args:
        city: Ciudad a validar

    Returns:
        Tupla (es_válido, mensaje_error)
    """
    from utils.services_utils import normalize_city_input

    if len(city) < MIN_CIUDAD_CHARS:
        return False, "*Indicame tu ciudad (ej: Quito, Guayaquil, Cuenca).*"

    # Normalizar y validar contra lista de ciudades de Ecuador
    canonical_city = normalize_city_input(city)

    if not canonical_city:
        return False, (
            "*No reconozco esa ciudad. Debe ser una ciudad de Ecuador.*\n"
            "*Ejemplos: Quito, Guayaquil, Cuenca, Ambato, Manta.*"
        )

    return True, None


def validate_name(name: str) -> Tuple[bool, Optional[str]]:
    """
    Valida nombre del proveedor.

    Validaciones:
    - Solo permite letras, espacios y acentos
    - No permite números
    - No permite caracteres especiales (@, #, $, etc.)
    - Mínimo 2 caracteres

    Args:
        name: Nombre a validar

    Returns:
        Tupla (es_válido, mensaje_error)
    """
    if len(name) < MIN_NOMBRE_CHARS:
        return False, "*Por favor, enviame tu nombre completo.*"

    # Verificar que contenga al menos una letra
    has_letter = any(c.isalpha() for c in name)
    if not has_letter:
        return False, "*El nombre debe contener al menos una letra.*"

    # Verificar caracteres permitidos: letras, espacios, acentos, apóstrofes
    allowed_chars_pattern = r"^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s'\-]+$"
    if not re.match(allowed_chars_pattern, name):
        return False, (
            "*El nombre solo puede contener letras y espacios.* "
            "No números ni símbolos (ej: Juan Pérez)."
        )

    # Verificar que no sea solo espacios
    if name.strip().isspace() or not name.strip():
        return False, "*Por favor, enviame tu nombre completo.*"

    return True, None


def validate_profession(profession: str) -> Tuple[bool, Optional[str]]:
    """
    Valida profesión del proveedor.

    Validaciones:
    - No permite emails (detecta @)
    - No permite URLs (http, https, www)
    - Longitud entre 2 y 150 caracteres
    - Debe contener al menos una letra

    Args:
        profession: Profesión a validar

    Returns:
        Tupla (es_válido, mensaje_error)
    """
    if len(profession) < MIN_PROFESION_CHARS:
        return False, (
            '*Indica tu profesión u oficio. Ejemplos: "Carpintero", '
            '"Ingeniero Electrico", "Abogado".*'
        )

    if len(profession) > MAX_PROFESION_CHARS:
        return False, (
            "*Tu profesión debe ser breve (máximo 150 caracteres).* "
            "Envía una versión resumida (ej: 'Ingeniera en marketing' o 'Contratación pública')."
        )

    # Detectar email (@)
    if "@" in profession.lower():
        return False, (
            "*La profesión no puede ser un correo electrónico.* "
            "Por favor indica tu profesión u oficio (ej: 'Carpintero', 'Ingeniero', 'Abogado')."
        )

    # Detectar URLs
    lowered = profession.lower()
    url_patterns = ["http://", "https://", "www.", ".com", ".edu", ".org", ".net"]
    if any(pattern in lowered for pattern in url_patterns):
        return False, (
            "*La profesión no puede ser una URL o enlace web.* "
            "Por favor indica tu profesión u oficio (ej: 'Carpintero', 'Ingeniero', 'Abogado')."
        )

    # Verificar que contenga al menos una letra (no solo números/símbolos)
    has_letter = any(c.isalpha() for c in profession)
    if not has_letter:
        return False, (
            "*La profesión debe contener al menos una letra.* "
            "Ejemplo: 'Carpintero', 'Ingeniero', 'Abogado'."
        )

    return True, None


def validate_specialty(specialty: str) -> Tuple[bool, Optional[str]]:
    """
    Valida especialidad/servicios del proveedor.

    Args:
        specialty: Especialidad a validar

    Returns:
        Tupla (es_válido, mensaje_error)
    """
    lowered = specialty.lower()
    if lowered in OMISSION_VALUES:
        return False, (
            "*La especialidad es obligatoria. Por favor escríbela tal como la trabajas, "
            "separando con comas si hay varias.*"
        )

    if len(specialty) < MIN_ESPECIALIDAD_CHARS:
        return False, (
            "*La especialidad debe tener al menos 2 caracteres. "
            "Incluye tus servicios separados por comas (ej: gasfitería, mantenimiento).*"
        )

    if len(specialty) > MAX_ESPECIALIDAD_CHARS:
        return False, (
            "*El listado de servicios es muy largo (máx. 300 caracteres).* "
            "Envía una versión resumida con tus principales servicios separados por comas."
        )

    services_list = [
        item.strip()
        for item in re.split(r"[;,/\n]+", specialty)
        if item and item.strip()
    ]

    if len(services_list) > SERVICIOS_MAXIMOS:
        return False, (
            f"*Incluye máximo {SERVICIOS_MAXIMOS} servicios.* Envía nuevamente tus principales servicios separados por comas."
        )

    if any(len(srv) > MAX_SERVICIO_CHARS for srv in services_list):
        return False, (
            "*Cada servicio debe ser breve (máx. 120 caracteres).* "
            "Recorta descripciones muy largas y envía de nuevo la lista."
        )

    return True, None


def validate_email(email: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Valida email del proveedor con regex mejorado.

    Validaciones:
    - Formato de email válido (regex)
    - Opción de omitir ("omitir", "na", "n/a", etc.)
    - Normalizado a minúsculas

    Args:
        email: Email a validar

    Returns:
        Tupla (es_válido, mensaje_error, email_normalizado)
        - email_normalizado puede ser None si el usuario quiere omitir
    """
    normalized = normalize_text(email)

    # Verificar si quiere omitir
    if normalized.lower() in OMISSION_VALUES:
        return True, None, None

    # Regex mejorado para email
    email_regex = re.compile(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    )

    if not email_regex.match(normalized):
        return False, (
            "*El correo no parece valido. Debe tener formato:* "
            "*usuario@dominio.com* "
            "*Envialo nuevamente o escribe 'omitir'.*"
        ), normalized

    return True, None, normalized.lower()


def validate_provider_payload(
    flow: Dict[str, Any], phone: str
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Valida y crea payload de proveedor usando Pydantic.

    Args:
        flow: Diccionario con datos del flujo
        phone: Teléfono del proveedor

    Returns:
        Tupla (es_válido, provider_payload como Dict o error_response)
    """
    specialty = flow.get("specialty")
    services_list = []
    if isinstance(specialty, str):
        services_list = [
            item.strip()
            for item in re.split(r"[;,/\n]+", specialty)
            if item and item.strip()
        ]
        if not services_list and specialty.strip():
            services_list = [specialty.strip()]

    try:
        provider_create = ProviderCreate(
            phone=phone,
            full_name=flow.get("name") or "",
            email=flow.get("email"),
            city=flow.get("city") or "",
            profession=flow.get("profession") or "",
            services_list=services_list,
            experience_years=flow.get("experience_years"),
            has_consent=flow.get("has_consent", False),
            social_media_url=flow.get("social_media_url"),
            social_media_type=flow.get("social_media_type"),
            # Campos para manejar phones tipo @lid
            real_phone=flow.get("real_phone"),
            phone_verified=flow.get("phone_verified"),
        )
        # Convertir a dict para compatibilidad con el tipo de retorno
        return True, provider_create.model_dump()
    except ValidationError as exc:
        logger.error("Datos de registro invalidos para %s: %s", phone, exc)
        first_error = exc.errors()[0] if exc.errors() else {}
        reason = first_error.get("msg") or "Datos inválidos"
        error_response = {
            "success": False,
            "response": (
                f"*No pude validar tus datos:* {reason}. "
                "Revisa que nombre, ciudad y profesión cumplan con el formato y longitud."
            ),
        }
        return False, error_response
