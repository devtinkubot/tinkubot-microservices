"""Servicio de validación de datos de proveedores."""
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError
from shared_lib.models import ProviderCreate

logger = logging.getLogger(__name__)

# Constantes de validación
MIN_CIUDAD_CHARS = 2
MIN_NOMBRE_CHARS = 2
MIN_PROFESION_CHARS = 2
MAX_PROFESION_CHARS = 150
MIN_ESPECIALIDAD_CHARS = 2
MAX_ESPECIALIDAD_CHARS = 300
MAX_SERVICIOS_COUNT = 10
MAX_SERVICIO_CHARS = 120
MIN_EXPERIENCE_YEARS = 0
MAX_EXPERIENCE_YEARS = 60

# Valores de omisión
OMISSION_VALUES = {"omitir", "na", "n/a", "ninguno", "ninguna"}


def normalize_text(value: Optional[str]) -> str:
    """
    Normaliza texto eliminando espacios en blanco.

    Args:
        value: Texto a normalizar

    Returns:
        Texto sin espacios al inicio y final, o cadena vacía si es None
    """
    return (value or "").strip()


def parse_experience_years(text: Optional[str]) -> Optional[int]:
    """
    Parsea años de experiencia desde texto.

    Args:
        text: Texto que contiene un número

    Returns:
        Entero entre 0 y 60, o None si no se puede parsear
    """
    normalized = (text or "").strip().lower()
    if not normalized:
        return None

    digits = ""
    for ch in normalized:
        if ch.isdigit():
            digits += ch
        elif digits:
            break

    if not digits:
        return None

    try:
        value = int(digits)
    except ValueError:
        return None

    return max(MIN_EXPERIENCE_YEARS, min(MAX_EXPERIENCE_YEARS, value))


def validate_city(city: str) -> Tuple[bool, Optional[str]]:
    """
    Valida ciudad del proveedor.

    Args:
        city: Ciudad a validar

    Returns:
        Tupla (es_válido, mensaje_error)
    """
    if len(city) < MIN_CIUDAD_CHARS:
        return False, f"*Indicame tu ciudad (ej: Quito, Guayaquil, Cuenca).*"
    return True, None


def validate_name(name: str) -> Tuple[bool, Optional[str]]:
    """
    Valida nombre del proveedor.

    Args:
        name: Nombre a validar

    Returns:
        Tupla (es_válido, mensaje_error)
    """
    if len(name) < MIN_NOMBRE_CHARS:
        return False, "*Por favor, enviame tu nombre completo.*"
    return True, None


def validate_profession(profession: str) -> Tuple[bool, Optional[str]]:
    """
    Valida profesión del proveedor.

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

    if len(services_list) > MAX_SERVICIOS_COUNT:
        return False, (
            "*Incluye máximo 10 servicios.* Envía nuevamente tus principales servicios separados por comas."
        )

    if any(len(srv) > MAX_SERVICIO_CHARS for srv in services_list):
        return False, (
            "*Cada servicio debe ser breve (máx. 120 caracteres).* "
            "Recorta descripciones muy largas y envía de nuevo la lista."
        )

    return True, None


def validate_email(email: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Valida email del proveedor.

    Args:
        email: Email a validar

    Returns:
        Tupla (es_válido, mensaje_error, email_normalizado)
        - email_normalizado puede ser None si el usuario quiere omitir
    """
    normalized = normalize_text(email)
    if normalized.lower() in OMISSION_VALUES:
        return True, None, None

    if "@" not in normalized or "." not in normalized:
        return False, (
            "*El correo no parece valido. Envialo nuevamente o escribe 'omitir'.*"
        ), normalized

    return True, None, normalized


def parse_social_media(message_text: Optional[str]) -> Dict[str, Optional[str]]:
    """
    Parsea la entrada de red social y devuelve url + tipo.

    Args:
        message_text: Texto con URL o nombre de usuario

    Returns:
        Dict con keys: 'url', 'type'
    """
    social = normalize_text(message_text)
    if social.lower() in OMISSION_VALUES:
        return {"url": None, "type": None}
    if "facebook.com" in social or "fb.com" in social:
        return {"url": social, "type": "facebook"}
    if "instagram.com" in social or "instagr.am" in social:
        return {"url": social, "type": "instagram"}
    return {"url": f"https://instagram.com/{social}", "type": "instagram"}


def validate_provider_payload(
    flow: Dict[str, Any], phone: str
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Valida y crea payload de proveedor usando Pydantic.

    Args:
        flow: Diccionario con datos del flujo
        phone: Teléfono del proveedor

    Returns:
        Tupla (es_válido, provider_payload o error_response)
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
        provider_payload = ProviderCreate(
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
        )
        return True, provider_payload
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


def parse_services_string(value: Optional[str]) -> List[str]:
    """
    Parsea cadena de servicios separados por separadores.

    Args:
        value: Cadena con servicios separados por |;,\n

    Returns:
        Lista de servicios (máximo 5)
    """
    if not value:
        return []

    cleaned = value.strip()
    if not cleaned:
        return []

    if re.search(r"[|;,\n]", cleaned):
        candidates = re.split(r"[|;,\n]+", cleaned)
    else:
        candidates = [cleaned]

    servicios: List[str] = []
    for item in candidates:
        servicio = item.strip()
        if servicio and servicio not in servicios:
            servicios.append(servicio)
    return servicios[:5]
