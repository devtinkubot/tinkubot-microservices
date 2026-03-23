"""Funciones de normalización de datos de proveedores."""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional

from models.proveedores import SolicitudCreacionProveedor
from services.servicios_proveedor.constantes import SERVICIOS_MAXIMOS
from services.servicios_proveedor.estado_operativo import (
    formatear_rango_experiencia,
    normalizar_experiencia,
)
from services.servicios_proveedor.redes_sociales_slots import resolver_redes_sociales
from services.servicios_proveedor.utilidades import (
    normalizar_texto_para_busqueda,
)
from services.servicios_proveedor.utilidades import (
    sanitizar_lista_servicios as sanitizar_servicios,
)

_CONECTORES_TITULO = {
    "a",
    "al",
    "con",
    "contra",
    "de",
    "del",
    "e",
    "el",
    "en",
    "la",
    "las",
    "los",
    "o",
    "para",
    "por",
    "sin",
    "u",
    "y",
}


def _normalizar_telefono_ecuador(telefono: str) -> str:
    """
    Normaliza números ecuatorianos a formato internacional 593.

    - 09xxxxxxxx → 5939xxxxxxxx (10 dígitos, empieza con 09)
    - 593xxxxxxxx → sin cambios (ya normalizado)
    - +593xxxxxxxx → 593xxxxxxxx (remueve prefijo +)
    """
    if not telefono:
        return telefono

    # Remover prefijo + si existe
    if telefono.startswith("+"):
        telefono = telefono[1:]

    # Convertir formato local 09... a internacional 5939...
    if len(telefono) == 10 and telefono.startswith("09"):
        telefono = "5939" + telefono[2:]

    return telefono


def _normalizar_jid_whatsapp(telefono: str) -> str:
    """
    Normaliza identidad de WhatsApp a formato JID completo user@server.

    Si no viene servidor, asume s.whatsapp.net para compatibilidad de registro.
    """
    valor = (telefono or "").strip()
    if not valor:
        return valor

    if "@" in valor:
        user, server = valor.split("@", 1)
        user = user.strip()
        server = server.strip().lower()
        if user and server:
            return f"{user}@{server}"
        return valor

    return f"{valor}@s.whatsapp.net"


def _formatear_servicio_para_visualizacion(servicio: str) -> str:
    """Genera una versión legible del servicio sin volverlo telegráfico."""
    texto = " ".join((servicio or "").strip().split())
    if not texto:
        return ""

    palabras = texto.lower().split()
    if not palabras:
        return ""

    resultado: List[str] = []
    for idx, palabra in enumerate(palabras):
        if idx > 0 and palabra in _CONECTORES_TITULO:
            resultado.append(palabra)
            continue
        resultado.append(palabra.capitalize())
    return " ".join(resultado)


def normalizar_datos_proveedor(
    datos_crudos: SolicitudCreacionProveedor,
) -> Dict[str, Any]:
    """
    Normaliza datos del formulario para el esquema unificado.

    Fase 5: Eliminado campo 'profession' y actualizada lógica de servicios.
    Ahora se retorna una lista de servicios normalizados
    en lugar de un string formateado.

    Args:
        datos_crudos: Datos crudos del proveedor desde el formulario

    Returns:
        Dict con datos normalizados según el esquema unificado

    Raises:
        ValueError: Si supera el máximo permitido
    """
    servicios = datos_crudos.services_list or []
    if len(servicios) > SERVICIOS_MAXIMOS:
        raise ValueError(f"Máximo {SERVICIOS_MAXIMOS} servicios permitidos")

    # Fase 5: Normalizar servicios preservando una variante legible y el texto original.
    servicios_limpios = sanitizar_servicios(servicios)
    servicios_normalizados = [
        _formatear_servicio_para_visualizacion(servicio)
        for servicio in servicios_limpios
        if servicio.strip()
    ]
    service_entries = []
    for idx, servicio_normalizado in enumerate(servicios_normalizados):
        raw_text = servicios_limpios[idx].strip() if idx < len(servicios_limpios) else ""
        service_entries.append(
            {
                "raw_service_text": raw_text or servicio_normalizado,
                "service_name": servicio_normalizado,
                "service_summary": "",
            }
        )

    telefono = _normalizar_jid_whatsapp(datos_crudos.phone.strip())
    real_phone = (
        _normalizar_telefono_ecuador(datos_crudos.real_phone.strip())
        if datos_crudos.real_phone
        else None
    )
    if not real_phone and telefono.endswith("@s.whatsapp.net"):
        user = telefono.split("@", 1)[0]
        if re.fullmatch(r"\+?\d{10,20}", user or ""):
            real_phone = _normalizar_telefono_ecuador(user)

    ahora_iso = datetime.now(timezone.utc).isoformat()
    tiene_coordenadas = (
        datos_crudos.location_lat is not None and datos_crudos.location_lng is not None
    )
    redes_sociales = resolver_redes_sociales(
        {
            "social_media_url": datos_crudos.social_media_url,
            "social_media_type": datos_crudos.social_media_type,
        }
    )

    return {
        "phone": telefono,
        "real_phone": real_phone,
        "full_name": datos_crudos.full_name.strip().title(),  # Formato legible
        "document_first_names": (
            datos_crudos.document_first_names.strip()
            if datos_crudos.document_first_names
            else None
        ),
        "document_last_names": (
            datos_crudos.document_last_names.strip()
            if datos_crudos.document_last_names
            else None
        ),
        "document_id_number": (
            datos_crudos.document_id_number.strip()
            if datos_crudos.document_id_number
            else None
        ),
        "city": normalizar_texto_para_busqueda(datos_crudos.city),  # minúsculas
        "location_lat": datos_crudos.location_lat,
        "location_lng": datos_crudos.location_lng,
        "location_updated_at": ahora_iso if tiene_coordenadas else None,
        "city_confirmed_at": ahora_iso,
        # Fase 5: Eliminado campo 'profession'
        "services_normalized": servicios_normalizados,  # Fase 5: Lista, no string
        "service_entries": service_entries,
        "experience_years": datos_crudos.experience_years or 0,
        "experience_range": formatear_rango_experiencia(
            normalizar_experiencia(datos_crudos.experience_years)
        ),
        "has_consent": datos_crudos.has_consent,
        "verified": False,
        # Arrancamos en 5 para promediar con futuras calificaciones de clientes.
        "rating": 5.0,
        "social_media_url": datos_crudos.social_media_url,
        "social_media_type": datos_crudos.social_media_type,
        "facebook_username": redes_sociales["facebook_username"],
        "instagram_username": redes_sociales["instagram_username"],
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
    datos["experience_range"] = datos.get("experience_range") or formatear_rango_experiencia(
        datos["experience_years"]
    )
    datos.setdefault("location_lat", None)
    datos.setdefault("location_lng", None)
    datos.setdefault("location_updated_at", None)
    datos.setdefault("city_confirmed_at", None)
    datos.setdefault("onboarding_step", None)
    datos.setdefault("onboarding_step_updated_at", None)
    datos.setdefault("facebook_username", None)
    datos.setdefault("instagram_username", None)
    # Fase 5: Eliminada referencia a 'profession'
    datos["has_consent"] = bool(datos.get("has_consent"))
    if not datos.get("status"):
        datos["status"] = "approved" if datos.get("verified") else "pending"
    return datos
